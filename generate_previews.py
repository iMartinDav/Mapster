import os
import argparse
from create_map_poster import MapPosterGenerator
import time

def generate_previews():
    generator = MapPosterGenerator()
    themes = generator.get_available_themes()
    
    # Use Barcelona for previews - it has a great grid structure that shows off themes well
    CITY = "Barcelona"
    COUNTRY = "Spain"
    DISTANCE = 6000
    
    output_dir = os.path.join("frontend", "public", "themes")
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Generating previews for {len(themes)} themes...")
    print(f"Location: {CITY}, {COUNTRY}")
    
    # Cache coordinates once
    try:
        coords = generator.get_coordinates(CITY, COUNTRY)
    except Exception as e:
        print(f"Failed to get coordinates: {e}")
        return

    for theme in themes:
        print(f"\nProcessing theme: {theme}")
        output_file = os.path.join(output_dir, f"{theme}.png")
        
        if os.path.exists(output_file):
            print(f"  Preview already exists: {output_file}")
            continue
            
        try:
            # Generate directly using internal methods to control output path/size better if needed
            # For now, we utilize the standard generation but rename/move result or modify logic
            # To keep it simple, we'll use the public API but we might want to scale it down in standard usage
            # Actually, standard generation is fine, we just need to ensure filename is correct
            
            # We need to bypass the standard timestamped filename generation in generate_poster
            # So we will modify the generator to accept an explicit output path or handling it here
            
            # Since generate_poster creates its own filename, we'll do a slight workaround or 
            # better yet, instantiate a slightly modified flow here using the generator's methods
            
            # Let's instantiate the map creation directly to control the output filename
            theme_data = generator.load_theme(theme)
            
            # Borrowing logic from generator.generate_poster but with fixed filename
            import matplotlib.pyplot as plt
            import osmnx as ox
            
            # We can't easily reuse generator.generate_poster signatures without modification
            # So let's modify the generator class in a separate step or just rely on it returning the path
            # and then renaming it, but that's wasteful.
            
            # Cleaner approach: The user wants to see what the theme looks like. 
            # I will just run the generator and move the file.
            
            generated_path = generator.generate_poster(CITY, COUNTRY, theme, DISTANCE)
            
            # Resize and move to preview folder
            if generated_path and os.path.exists(generated_path):
                try:
                    from PIL import Image
                    with Image.open(generated_path) as img:
                        # Calculate new height maintaining aspect ratio
                        width = 400
                        height = int((float(img.size[1]) * float(width)) / float(img.size[0]))
                        img = img.resize((width, height), Image.Resampling.LANCZOS)
                        img.save(output_file, optimize=True, quality=85)
                    
                    # Clean up original large file
                    os.remove(generated_path)
                    print(f"  Saved resized preview to: {output_file}")
                except ImportError:
                    print("  PIL not installed, moving original file")
                    os.replace(generated_path, output_file)
                
        except Exception as e:
            print(f"  Failed to generate preview for {theme}: {e}")

if __name__ == "__main__":
    generate_previews()
