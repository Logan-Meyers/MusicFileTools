import sys
from pathlib import Path
from mutagen.mp4 import MP4

def update_m4a_metadata(folder_path, album_name):
    folder = Path(folder_path)
    
    if not folder.is_dir():
        print(f"Error: {folder_path} is not a valid directory")
        sys.exit(1)
    
    for m4a_file in folder.glob("*.m4a"):
        try:
            audio = MP4(m4a_file)
            
            # Remove album tag
            if '\xa9alb' in audio:
                del audio['\xa9alb']
            
            # Set new album if provided
            if album_name:
                audio['\xa9alb'] = album_name
            
            audio.save()
            print(f"✓ {m4a_file.name}")
        except Exception as e:
            print(f"✗ {m4a_file.name}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python script.py set <folder> [album_name]")
        print("  python script.py del <folder>")
        sys.exit(1)
    
    command = sys.argv[1]
    folder_path = sys.argv[2]
    
    if command == "set":
        # Use provided album name, or fall back to parent folder name
        album_name = sys.argv[3] if len(sys.argv) > 3 else Path(folder_path).name
        update_m4a_metadata(folder_path, album_name)
        print(f"Album set to: {album_name}")
    
    elif command == "del":
        update_m4a_metadata(folder_path, None)
        print("Album tags removed")
    
    else:
        print(f"Unknown command: {command}")
        print("Use 'set' or 'del'")
        sys.exit(1)