**************************************************************************************************************************
HeliCraft is a Python tool for generating and arranging molecular structures along various types of helical paths, such as 
cylindrical, conical, Archimedean, Fibonacci, and golden spirals. It reads atomic coordinates from an XYZ file, places the 
structures on a helical surface, and applies transformations to align them with the spiral's geometry. The output is saved 
as XYZ files for visualization or further analysis.

** Features **
1) Supports multiple spiral types: cylindrical, conical, Archimedean, Fibonacci, and golden spirals, with left- or right-
   handed chirality;
3) Generates grid points on the spiral surface for structure placement;
4) Aligns molecular structures using reference points and vectors, with options for normal vector orientation (perpendicu-
   lar or parallel to the helical axis);
6) Validates transformations to ensure interatomic distances are preserved;
7) Saves transformed structures as individual frames or a combined XYZ file;
8) Provides debugging information through a structure info file.

** Prerequisites **
1) Python 3.6+
2) numpy
3) pandas
4) scipy

** Install dependencies using **
   pip install numpy pandas scipy

** Installation **
   Clone the repository:
   git clone https://github.com/GraceJunhao/HeliCraft.git
   cd HeliCraft

Ensure all required Python modules (Main.py, Mod1.py, Mod2.py, Mod3.py, Mod4.py, Mod5.py, Mod6.py, Mod7.py) are in the 
same directory.

** Usage **
1) Prepare an XYZ file:
   Create an XYZ file containing the atomic coordinates of the molecular structure to be placed on the spiral. The file
   should follow the standard XYZ format:
                      <number of atoms>
                      <comment line>
                      <symbol> <x> <y> <z>
                      ...
3) Run the program:
   python Main.py
4) Follow the prompts:
   3.1) Select a spiral type (e.g., right-handed cylindrical spiral);
   3.2) Enter spiral parameters (e.g., radius, pitch, number of turns, bandwidth, grid size);
   3.3) Choose the orientation of the spiral's normal vector (perpendicular or parallel to the helical axis);
   3.4) Provide the path to the XYZ file;
   3.5) Select two atoms to define the reference vector for alignment;
   3.6) Specify output filenames for the frame-by-frame and combined XYZ files (default: PRO_frame.xyz and PRO_all.xyz).
5) Outputs:
   5.1) spiral_points.csv: Grid points generated on the spiral surface;
   5.2) <output_file_frame>.xyz: Frame-by-frame XYZ file for animation or analysis;
   5.3) <output_file_all>.xyz: Combined XYZ file containing all transformed structures;
   5.4) structure_info.txt: Debugging file with structure information.

** Notes **
1) The program assumes the spiral axis is along the z-axis;
2) Grid points are uniformly distributed on the spiral surface, with the number of structures determined by the surface area
   and grid size;
3) Chirality (left- or right-handed) affects the spiral's rotation direction;
4) The transformation ensures that interatomic distances are preserved, with validation performed automatically.

** License **
This project is licensed under the MIT License. See the LICENSE file for details.

** Citation **
The original paper on HeliCraft is currently under submission. 
If you use HeliCraft in your research, please cite the original paper once it is published. 
Thank you very much!!!



