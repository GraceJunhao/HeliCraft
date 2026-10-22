# HeliCraft
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23552339.svg)](https://doi.org/10.5281/zenodo.23552339)

HeliCraft constructs helical and ribbon molecular arrangements from a user-supplied
XYZ template. Users specify a scaffold and the placement of rigid template copies,
inspect the resulting coordinates, and export an initial arrangement for subsequent
analysis or simulation preparation.

- Hosted workspace: <https://www.helicraft-lab.cn/>
- Source repository: <https://github.com/GraceJunhao/HeliCraft>
- Source license: [MIT](LICENSE)

## Construction workflow

1. Supply an XYZ template and select reference sites A and B using zero-based indices.
2. Choose a cylindrical, conical, Archimedean, exponentially expanding, flat-ribbon,
   or twisted-ribbon scaffold and set its dimensions and sampling parameters.
3. Set winding direction where applicable, local insertion angle, and supported
   multi-strand controls. Flat scaffolds do not acquire handedness from a winding selector.
4. Build the coordinates. The browser uses XYZ for molecular preview and offers
   coordinate exports including XYZ, PDB and mmCIF, with construction metadata.

Jack provides an additional route for explaining controls and proposing form changes.
The user reviews and accepts a proposal before a separate Build action constructs
coordinates. The model service uses operator-supplied credentials; no credentials or
account data from the hosted service are included in this distribution.

## Scope

The same placement engine can use all-atom or coarse-grained templates. It preserves
the supplied internal conformation through rigid placement. Contact diagnostics help
inspect initial arrangements but do not establish physical stability. The sampling
interval L is not a collision threshold. Molecular interactions, force-field assignment,
relaxation and simulation remain separate preparation and analysis steps.

## Local installation

Use an isolated Python environment. The deployment used Python 3.8; the dependency
file lists required packages rather than an exact environment lock. Validate a fresh
installation on the Python version you intend to use.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Fill in your own SMTP settings and a fresh session secret in `.env`. Jack additionally
requires a provider key and model identifier. See [configuration instructions](CONFIGURATION.md).

```sh
python -m uvicorn web_opi:app --host 127.0.0.1 --port 8081 --env-file .env
```

Run this command from the extracted HeliCraft directory. The service creates its own
local user database; the hosted service's database is not distributed. The email-login
workflow needs a functioning SMTP configuration. Local startup does not reproduce a
production deployment with HTTPS, a reverse proxy, backups and process supervision.

## Release provenance

`release_info.py` contains component identifiers. `SOURCE_MANIFEST.json` records the
distribution label, the files actually packaged, their SHA256 values, and configuration
changes made only in the release copy. A packaging date does not imply a new geometry
engine version or renewed performance measurements.

This source-only snapshot excludes production configuration, user information, private
session records, generated molecular files, historical patches and artwork. Research
templates, figure coordinates and benchmark records should be deposited separately
with their own provenance and permissions. No persistent archive DOI is asserted here.

Dependencies and any separately obtained third-party assets retain their own licenses.
