import sys
from pathlib import Path
from mutagen.mp4 import MP4, MP4Cover
import requests
from io import BytesIO
from PIL import Image
import time
import urllib.parse

def search_musicbrainz(title, artist):
    """Search MusicBrainz for recording"""
    query_parts = []
    if title:
        query_parts.append(f'recording:"{title}"')
    if artist:
        query_parts.append(f'artist:"{artist}"')
    
    if not query_parts:
        return None
    
    query = ' AND '.join(query_parts)
    url = f"https://musicbrainz.org/ws/2/recording/?query={urllib.parse.quote(query)}&fmt=json&limit=1"
    
    headers = {
        'User-Agent': 'AlbumArtFetcher/1.0 (personal use)'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('recordings'):
                recording = data['recordings'][0]
                # Get release (album) ID
                if recording.get('releases'):
                    release_id = recording['releases'][0]['id']
                    return release_id
        return None
    except Exception as e:
        print(f"  MusicBrainz error: {e}")
        return None

def get_cover_art(release_id):
    """Get cover art from Cover Art Archive"""
    url = f"https://coverartarchive.org/release/{release_id}/front"
    
    try:
        response = requests.get(url, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            return response.content
        return None
    except Exception as e:
        print(f"  Cover Art Archive error: {e}")
        return None

def search_album_art(title, artist):
    """
    Search for album art using MusicBrainz + Cover Art Archive
    """
    print(f"  Searching MusicBrainz...")
    release_id = search_musicbrainz(title, artist)
    
    if not release_id:
        print(f"  No recording found")
        return None
    
    print(f"  Found release, fetching cover art...")
    cover_data = get_cover_art(release_id)
    
    if cover_data:
        return cover_data
    
    print(f"  No cover art available")
    return None

def load_local_cover(folder_path):
    """Look for cover.jpg in the folder"""
    folder = Path(folder_path)
    cover_file = folder / "cover.jpg"
    
    if cover_file.exists():
        try:
            with open(cover_file, 'rb') as f:
                return f.read()
        except Exception as e:
            print(f"  Failed to read cover.jpg: {e}")
    
    return None

def resize_image(image_data, max_size=512):
    """Resize image data"""
    try:
        img = Image.open(BytesIO(image_data))
        
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        output = BytesIO()
        img.save(output, format='JPEG', quality=95)
        return output.getvalue()
    except Exception as e:
        print(f"  Failed to process image: {e}")
        return None

def create_default_artwork(max_size=512):
    """Create a simple gray default album art"""
    img = Image.new('RGB', (max_size, max_size), color=(50, 50, 50))
    output = BytesIO()
    img.save(output, format='JPEG', quality=95)
    return output.getvalue()

def add_album_art_to_folder(folder_path):
    """Use same artwork for all songs in folder"""
    folder = Path(folder_path)
    
    if not folder.is_dir():
        print(f"Error: {folder_path} is not a valid directory")
        return 0, 0
    
    m4a_files = list(folder.glob("*.m4a"))
    
    if not m4a_files:
        print("No .m4a files found in folder")
        return 0, 0
    
    succeeded = 0
    failed = 0
    used_local_cover = False
    
    # First, check for local cover.jpg
    print("Looking for cover.jpg...")
    image_data = load_local_cover(folder_path)
    
    if image_data:
        print("Found cover.jpg, using local artwork")
        image_data = resize_image(image_data)
        used_local_cover = True
    else:
        print("No cover.jpg found, searching online...")
        
        # Use first file to get album info
        try:
            audio = MP4(m4a_files[0])
            album = audio.get('\xa9alb', [None])[0] if '\xa9alb' in audio else None
            artist = audio.get('\xa9ART', [None])[0] if '\xa9ART' in audio else None
            title = audio.get('\xa9nam', [None])[0] if '\xa9nam' in audio else None
            
            # For album mode, prefer album name
            if album:
                search_title = album
                search_artist = artist
            elif title:
                search_title = title
                search_artist = artist
            else:
                search_title = folder.name
                search_artist = None
            
            print(f"Searching for: {search_title}" + (f" by {search_artist}" if search_artist else ""))
            
        except Exception as e:
            print(f"Could not read metadata, using folder name")
            search_title = folder.name
            search_artist = None
        
        image_data = search_album_art(search_title, search_artist)
        
        if image_data:
            print(f"Found artwork online, resizing...")
            image_data = resize_image(image_data)
    
    if not image_data:
        print("Using default artwork")
        image_data = create_default_artwork()
    
    # Apply to all m4a files
    for m4a_file in m4a_files:
        try:
            audio = MP4(m4a_file)
            audio['covr'] = [MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG)]
            audio.save()
            print(f"✓ {m4a_file.name}")
            succeeded += 1
        except Exception as e:
            print(f"✗ {m4a_file.name}: {e}")
            failed += 1
    
    # If all succeeded and we used local cover, delete cover.jpg
    if used_local_cover and failed == 0 and succeeded > 0:
        cover_file = folder / "cover.jpg"
        try:
            cover_file.unlink()
            print(f"\n✓ Deleted cover.jpg (all files processed successfully)")
        except Exception as e:
            print(f"\n⚠ Could not delete cover.jpg: {e}")
    
    print(f"\n--- Results ---")
    print(f"Succeeded: {succeeded}")
    print(f"Failed: {failed}")
    
    return succeeded, failed

def add_album_art_per_song(folder_path):
    """Search for artwork individually for each song"""
    folder = Path(folder_path)
    
    if not folder.is_dir():
        print(f"Error: {folder_path} is not a valid directory")
        return 0, 0
    
    m4a_files = list(folder.glob("*.m4a"))
    
    if not m4a_files:
        print("No .m4a files found in folder")
        return 0, 0
    
    succeeded = 0
    failed = 0
    default_artwork = create_default_artwork()
    
    for m4a_file in m4a_files:
        try:
            audio = MP4(m4a_file)
            
            # Build search query from song metadata
            title = audio.get('\xa9nam', [None])[0] if '\xa9nam' in audio else None
            artist = audio.get('\xa9ART', [None])[0] if '\xa9ART' in audio else None
            
            # If no metadata, try parsing filename (handle "Title - Artist" format)
            if not title and not artist:
                filename = m4a_file.stem
                if ' - ' in filename:
                    parts = filename.split(' - ', 1)
                    title = parts[0].strip()
                    artist = parts[1].strip()
                else:
                    title = filename
            
            print(f"\n{m4a_file.name}")
            print(f"Searching for: {title}" + (f" by {artist}" if artist else ""))
            
            image_data = search_album_art(title, artist)
            
            if image_data:
                image_data = resize_image(image_data)
            
            # Use default if search/download failed
            if not image_data:
                print(f"⚠ Using default artwork")
                image_data = default_artwork
                failed += 1
            else:
                succeeded += 1
            
            audio['covr'] = [MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG)]
            audio.save()
            print(f"✓ Saved")
            
            # Rate limit: MusicBrainz requests max 1 per second
            time.sleep(1.1)
            
        except Exception as e:
            print(f"✗ {m4a_file.name}: {e}")
            failed += 1
    
    print(f"\n--- Results ---")
    print(f"Succeeded: {succeeded}")
    print(f"Failed: {failed}")
    
    return succeeded, failed

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python script.py <folder1> [folder2] [folder3] ...        # Search for each song individually")
        print("  python script.py album <folder1> [folder2] [folder3] ...  # Use same artwork for entire folder")
        sys.exit(1)
    
    # Check if album mode
    is_album_mode = sys.argv[1] == "album"
    
    # Get folder list
    if is_album_mode:
        if len(sys.argv) < 3:
            print("Error: at least one folder path required after 'album'")
            sys.exit(1)
        folders = sys.argv[2:]
    else:
        folders = sys.argv[1:]
    
    # Track overall stats
    total_succeeded = 0
    total_failed = 0
    
    # Process each folder
    for i, folder_path in enumerate(folders, 1):
        print(f"\n{'='*60}")
        print(f"Processing folder {i}/{len(folders)}: {folder_path}")
        print(f"{'='*60}\n")
        
        if is_album_mode:
            s, f = add_album_art_to_folder(folder_path)
        else:
            s, f = add_album_art_per_song(folder_path)
        
        total_succeeded += s
        total_failed += f
    
    # Print overall summary if multiple folders
    if len(folders) > 1:
        print(f"\n{'='*60}")
        print(f"OVERALL SUMMARY")
        print(f"{'='*60}")
        print(f"Total folders processed: {len(folders)}")
        print(f"Total succeeded: {total_succeeded}")
        print(f"Total failed: {total_failed}")