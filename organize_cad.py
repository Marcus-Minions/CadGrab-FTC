import os
import shutil

DOWNLOAD_DIR = "CAD_Files"
UNCATEGORIZED_DIR = os.path.join(DOWNLOAD_DIR, "UNCATEGORIZED")

KEYWORD_CATEGORIES = {
    "motor controller": "ELECTRONICS", "servo controller": "ELECTRONICS", "spark": "ELECTRONICS",
    "sensor": "ELECTRONICS", "cable": "ELECTRONICS", "wire": "ELECTRONICS", "battery": "ELECTRONICS",
    "power": "ELECTRONICS", "switch": "ELECTRONICS", "control hub": "ELECTRONICS",
    "expansion hub": "ELECTRONICS", "camera": "ELECTRONICS", "vision": "ELECTRONICS", "logic level": "ELECTRONICS",
    "motor": "MOTION", "servo": "MOTION", "wheel": "MOTION", "gear": "MOTION", "sprocket": "MOTION",
    "pulley": "MOTION", "belt": "MOTION", "chain": "MOTION", "bearing": "MOTION", "shaft": "MOTION",
    "axle": "MOTION", "hub": "MOTION", "mecanum": "MOTION", "omni": "MOTION", "caster": "MOTION",
    "pinion": "MOTION", "gearbox": "MOTION", "linear": "MOTION", "lead screw": "MOTION",
    "channel": "STRUCTURE", "extrusion": "STRUCTURE", "tube": "STRUCTURE", "plate": "STRUCTURE",
    "bracket": "STRUCTURE", "mount": "STRUCTURE", "beam": "STRUCTURE", "rail": "STRUCTURE",
    "standoff": "STRUCTURE", "spacer": "STRUCTURE", "gusset": "STRUCTURE", "spline": "STRUCTURE",
    "screw": "HARDWARE", "nut": "HARDWARE", "bolt": "HARDWARE", "washer": "HARDWARE",
    "collar": "HARDWARE", "zip tie": "HARDWARE", "fastener": "HARDWARE", "spring": "HARDWARE",
    "bungee": "HARDWARE", "surgical tubing": "HARDWARE", "insert": "HARDWARE", "shim": "HARDWARE"
}

def guess_category_from_name(name: str) -> str:
    lower_name = name.lower()
    for kw, cat in KEYWORD_CATEGORIES.items():
        if kw in lower_name:
            return cat
    return "UNCATEGORIZED"

def organize():
    print("====================================")
    print("      CadGrab Folder Organizer      ")
    print("====================================")
    
    if not os.path.exists(UNCATEGORIZED_DIR):
        print(f"Directory {UNCATEGORIZED_DIR} does not exist. Nothing to organize.")
        return
        
    files = [f for f in os.listdir(UNCATEGORIZED_DIR) if f.lower().endswith('.step') or f.lower().endswith('.stp')]
    if not files:
        print("No CAD files found in the UNCATEGORIZED folder.")
        return
        
    print(f"Found {len(files)} files to organize.\n")
    
    moved_count = 0
    for filename in files:
        guessed_cat = guess_category_from_name(filename)
        if guessed_cat != "UNCATEGORIZED":
            source_path = os.path.join(UNCATEGORIZED_DIR, filename)
            target_dir = os.path.join(DOWNLOAD_DIR, guessed_cat)
            target_path = os.path.join(target_dir, filename)
            
            os.makedirs(target_dir, exist_ok=True)
            try:
                # To handle if a file already exists in the target directory
                if os.path.exists(target_path):
                    print(f"[SKIPPED] {filename} already exists in {guessed_cat}.")
                    os.remove(source_path) # Remove the duplicate in UNCATEGORIZED to clean it up
                else:
                    shutil.move(source_path, target_path)
                    print(f"Moved: {filename} -> {guessed_cat}")
                moved_count += 1
            except Exception as e:
                print(f"Failed to move {filename}: {e}")
                
    print(f"\nOrganization complete! Moved {moved_count} out of {len(files)} files into proper categories.")

if __name__ == "__main__":
    organize()
