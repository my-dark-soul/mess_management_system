import shutil
import os

def move_all_files():
    # Define source and destination directories
    src_dir = 'member_photo'
    dest_dir = 'static/member_photo'
    
    try:
        # Check if source directory exists
        if not os.path.exists(src_dir):
            print(f"Error: {src_dir} does not exist.")
            return
        
        # Create destination directory if it doesn't exist
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
            print(f"Created destination directory: {dest_dir}")

        # Iterate over all files in the source directory
        for filename in os.listdir(src_dir):
            src_path = os.path.join(src_dir, filename)
            dest_path = os.path.join(dest_dir, filename)
            
            # Check if it's a file (not a subdirectory)
            if os.path.isfile(src_path):
                # Move the file
                shutil.move(src_path, dest_path)
                print(f"Moved {filename} to {dest_dir}")
            else:
                print(f"Skipping {filename}, it is not a file.")
    
    except Exception as e:
        print(f"Error: {e}")
