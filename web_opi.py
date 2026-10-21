# HELICRAFT_ASSISTANT_V1
import tempfile
from helicraft_assistant import install, login_response
import os
import time
import random
import sqlite3
import shutil
import emails
import asyncio
from fastapi import FastAPI, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# --- 导入物理引擎 ---
try:
    from Main import CleanSpiralBuilder
    from config_models import SpiralConfig
except ImportError as e:
    print(f"🚩 导入错误: 请确保 Main.py 和 config_models.py 在当前目录。")

# ==========================================
# 🛡️ 核心配置与数据库
# ==========================================
SMTP_USER = __import__("os").environ.get("HELICRAFT_SMTP_USER", "")  # 你的 163 邮箱
SMTP_PASS = __import__("os").environ.get("HELICRAFT_SMTP_PASS", "")                # ⚠️ 这里必须填入你的 163 授权码
SMTP_HOST = __import__("os").environ.get("HELICRAFT_SMTP_HOST", "")

# 内存数据存储
verification_codes = {}  
ip_throttle = {}         
email_throttle = {}      
SEND_COOLDOWN = 60       
LOGIN_COOLDOWN = 7200    

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                     (email TEXT PRIMARY KEY, username TEXT, hashed_password TEXT)''')
    conn.commit()
    conn.close()

init_db()

app = FastAPI(title="HeliCraft API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- 核心路由拆分 ---
@app.get("/")
async def read_index(): return FileResponse('index.html')

@app.get("/app.html")
async def read_app(): return FileResponse('app.html')

app.mount("/static", StaticFiles(directory="static"), name="static")

# ==========================================
# 💌 邮件服务引擎 (后台异步，防卡顿)
# ==========================================
def send_email_task(target_email: str, subject: str, html_body: str):
    try:
        message = emails.Message(html=html_body, subject=subject, mail_from=("HeliCraft Node", SMTP_USER))
        message.send(to=target_email, smtp={'host': SMTP_HOST, 'port': 465, 'ssl': True, 'user': SMTP_USER, 'password': SMTP_PASS})
    except Exception as e:
        print(f"🚩 邮件发送失败: {str(e)}")

def trigger_crm_email(target_email: str, username: str, is_new_user: bool, background_tasks: BackgroundTasks):
    if is_new_user:
        subject = "【HeliCraft】欢迎加入超分子算力平台——戴君豪！"
        html_body = f"""<div style="font-family: sans-serif; padding: 30px; background: #f8fafc; border-radius: 12px; border: 1px solid #e2e8f0; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #0f172a; margin-top: 0;">HeliCraft Profile Created</h2>
            <p style="color: #334155;">尊敬的 <b>{username}</b> 研究员，您好：</p>
            <p style="color: #334155;">欢迎您激活 HeliCraft 算力档案。您的校园身份已核验完毕，系统权限已全部开放。</p>
            <hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 20px 0;"><p style="font-size: 12px; color: #94a3b8; margin: 0;">HeliCraft Core Engine | HPC Center</p></div>"""
    else:
        subject = "【HeliCraft】工作台登录通知 From 戴君豪"
        html_body = f"""<div style="font-family: sans-serif; padding: 30px; border-top: 4px solid #10b981; background: #ffffff; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto;">
            <h3 style="color: #0f172a; margin-top: 0;">HeliCraft Session Active</h3>
            <p style="color: #334155;">尊敬的 <b>{username}</b>，系统检测到您刚刚成功接入了核心控制台。</p>
            <p style="color: #64748b; font-size: 13px;">如果这是您本人的操作，请忽略此邮件。如非本人操作，请立刻联系管理员。</p>
            <hr style="border: 0; border-top: 1px dashed #e2e8f0; margin: 20px 0;"><p style="font-size: 12px; color: #94a3b8; margin: 0;">HeliCraft Security Team</p></div>"""
    background_tasks.add_task(send_email_task, target_email, subject, html_body)

# ==========================================
# 🛡️ 自研网关接口 (防刷、验证、注册)
# ==========================================
@app.post("/api/auth/send_code")
async def send_code(request: Request, background_tasks: BackgroundTasks, email_addr: str = Form(...)):
    client_ip = request.headers.get('CF-Connecting-IP') or request.client.host
    email_addr = email_addr.strip().lower()

    current_time = time.time()
    last_req = ip_throttle.get(client_ip, 0)
    if current_time - last_req < SEND_COOLDOWN:
        return JSONResponse({"status": "error", "message": f"请求频繁，请等待 {int(SEND_COOLDOWN - (current_time - last_req))} 秒"})

    ip_throttle[client_ip] = current_time
    code = f"{random.randint(100000, 999999)}"
    verification_codes[email_addr] = {"code": code, "expire": current_time + 300}

    html_body = f"""<div style="font-family: sans-serif; padding: 20px;">
        <h2>HeliCraft 身份核验</h2><p>您的动态验证码是：</p>
        <h1 style="color:#2563eb; letter-spacing: 5px;">{code}</h1><p>该验证码 5 分钟内有效。</p></div>"""
    background_tasks.add_task(send_email_task, email_addr, "【HeliCraft】您的验证码 From 戴君豪", html_body)
    return {"status": "success", "message": "验证码已发送，请查收邮件"}

@app.post("/api/auth/login")
async def verify_login(request: Request, background_tasks: BackgroundTasks, email: str = Form(...), code: str = Form(...)):
    email = email.strip().lower()
    record = verification_codes.get(email)
    if not record or record["code"] != code.strip() or time.time() > record["expire"]:
        return JSONResponse({"status": "error", "message": "验证码错误或已过期"})

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE email=?", (email,))
    user = cursor.fetchone()
    conn.close()

    if user:
        username = user[0]
        if time.time() - email_throttle.get(email, 0) > LOGIN_COOLDOWN:
            trigger_crm_email(email, username, False, background_tasks)
            email_throttle[email] = time.time()
        del verification_codes[email] 
        return login_response({"status": "success", "username": username}, email)
    else:
        return JSONResponse({"status": "error", "message": "尚未建立档案，请切换至【注册】页面"})

@app.post("/api/auth/register")
async def register_profile(request: Request, background_tasks: BackgroundTasks, email: str = Form(...), code: str = Form(...), username: str = Form(...)):
    email = email.strip().lower()
    record = verification_codes.get(email)
    if not record or record["code"] != code.strip() or time.time() > record["expire"]:
        return JSONResponse({"status": "error", "message": "验证身份失效，请重新获取验证码"})

    username = username.strip()
    if not username: return JSONResponse({"status": "error", "message": "姓名不能为空"})

    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users VALUES (?, ?, ?)", (email, username, ""))
        conn.commit()
        conn.close()
        trigger_crm_email(email, username, True, background_tasks)
        email_throttle[email] = time.time()
        del verification_codes[email]
        return login_response({"status": "success", "message": "档案激活成功", "username": username}, email)
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"服务器异常: {str(e)}"})

# ==========================================
# 🏗️ 分子构建引擎接口 (已修复参数断层与异常处理)
# ==========================================
@app.post("/api/build")
async def build_spiral(
    request: Request, 
    file: UploadFile = File(...), 
    spiral_type: str = Form(...),
    W: float = Form(35.0), 
    L: float = Form(4.0), 
    R: float = Form(15.0), 
    P: float = Form(10.0), 
    N: float = Form(3.0),
    a_idx: int = Form(0), 
    b_idx: int = Form(1),
    # 👇 下面是你之前漏掉接收的前端核心参数
    Rbase: float = Form(0.0),
    Rtop: float = Form(0.0),
    k: float = Form(0.0),
    Length: float = Form(0.0),
    twist_turns: float = Form(0.0),
    insertion_angle: float = Form(0.0),
    strand_count: int = Form(1, ge=1, le=12),
    strand_phase_deg: float = Form(0.0, ge=-360.0, le=360.0),
    contact_cutoff: float = Form(1.0, ge=0, le=100),
    save_cg: str = Form("false"),
    cg_template_name: str = Form("PLBB")
):
    from helicraft_assistant.api import require_session
    from release_info import RELEASE
    require_session(request)
    try:
        # Every request owns its input and output paths. Download content is
        # captured before cleanup, so another build cannot replace this result.
        with tempfile.TemporaryDirectory(prefix="helicraft-build-") as build_dir:
            temp_in = os.path.join(build_dir, "monomer.xyz")
            output_prefix = os.path.join(build_dir, "assembly")
            with open(temp_in, "wb") as f:
                content = await file.read(32 * 1024 * 1024 + 1)
                if len(content) > 32 * 1024 * 1024:
                    return JSONResponse({'status': 'error', 'message': 'Template exceeds 32 MiB.'}, status_code=413)
                f.write(content)

            config = SpiralConfig(
                spiral_type=spiral_type,
                xyz_file_path=temp_in,
                output_prefix=output_prefix,
                W=W, L=L, R=R, P=P, N=N, a_idx=a_idx, b_idx=b_idx,
                Rbase=Rbase, Rtop=Rtop, k=k, Length=Length, twist_turns=twist_turns,
                insertion_angle=insertion_angle,
                strand_count=strand_count, strand_phase_deg=strand_phase_deg,
                contact_cutoff=contact_cutoff,
                save_cg=(save_cg.lower() == 'true'),
                cg_template_name=cg_template_name
            )
            builder = CleanSpiralBuilder(config)
            builder.run()

            result = {
                "status": "success",
                "protocol": "helicraft-build-v2",
                "release": RELEASE,
                "sampling": builder.sampling_metadata,
                "contacts": builder.contact_report,
                "template_sha256": builder.template_sha256,
                "atom_count": sum(len(copy) for copy in builder.transformed_structures),
                "atoms_per_monomer": len(builder.atoms),
                "copy_count": len(builder.transformed_structures),
                "strand_count": config.strand_count,
                "copies_per_strand": builder.copies_per_strand,
                "strand_phase_deg": config.strand_phase_deg,
            }
            formats = ["xyz", "cif", "json"] + (["mst", "xml"] if config.save_cg else [])
            if builder.pdb_unavailable_reason:
                result["pdb_unavailable_reason"] = builder.pdb_unavailable_reason
            else:
                formats.append("pdb")
            for extension in formats:
                target_file = f"{output_prefix}_all.{extension}"
                with open(target_file, "r", encoding="utf-8", newline="") as f:
                    result[extension] = f.read()
            return result
        
    except ValueError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=422)
    except Exception as e:
        return JSONResponse({"status": "error", "message": "Construction failed. Check server logs and inputs."}, status_code=500)

# ==========================================
# 🧠 AI 智能拓扑推断接口 (Mock 模拟版)
# ==========================================

install(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_opi:app", host="127.0.0.1", port=8081, reload=True)