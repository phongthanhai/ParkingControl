import os
import cv2
import time
import uuid
import shutil
from datetime import datetime

class ImageStorage:
    """
    Utility for managing local storage of images captured by the system
    in offline mode. Ensures proper organization and cleanup of image files.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ImageStorage, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the image storage directories."""
        # Base storage path in project directory
        self.base_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'offline_images'
        )
        
        # Create organization structure
        self.entry_dir = os.path.join(self.base_dir, 'entry')
        self.exit_dir = os.path.join(self.base_dir, 'exit')
        self.blacklist_dir = os.path.join(self.base_dir, 'blacklist')
        
        # Create directories if they don't exist
        for directory in [self.base_dir, self.entry_dir, self.exit_dir, self.blacklist_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
        
        # Set image retention period (7 days by default)
        self.retention_days = 7
    
    def save_image(self, image, lane_type, plate_id=None, event_type=None):
        """
        Save an image to local storage with proper naming and organization.
        
        Args:
            image: OpenCV image (numpy array)
            lane_type: 'entry' or 'exit'
            plate_id: Vehicle plate ID (if available)
            event_type: Type of event ('auto', 'manual', 'denied-blacklist', etc.)
            
        Returns:
            str: Path to the saved image file, or None if save failed
        """
        try:
            # Determine the target directory
            if event_type == 'denied-blacklist':
                target_dir = self.blacklist_dir
            elif lane_type == 'entry':
                target_dir = self.entry_dir
            elif lane_type == 'exit':
                target_dir = self.exit_dir
            else:
                target_dir = self.base_dir
            
            # Create a unique filename with timestamp and plate ID
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            
            if plate_id:
                # Sanitize plate ID for filename
                safe_plate = plate_id.replace(' ', '_').replace('-', '_')
                filename = f"{timestamp}_{safe_plate}_{unique_id}.png"
            else:
                filename = f"{timestamp}_{lane_type}_{unique_id}.png"
            
            # Full path to save the image
            file_path = os.path.join(target_dir, filename)
            
            # Save the image
            if image is not None:
                success = cv2.imwrite(file_path, image)
                if success:
                    return file_path
            
            return None
            
        except Exception as e:
            print(f"Error saving image: {str(e)}")
            return None
    
    def cleanup_old_images(self):
        """Remove images older than the retention period."""
        try:
            now = time.time()
            retention_seconds = self.retention_days * 24 * 60 * 60
            
            for root, _, files in os.walk(self.base_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # Skip if not an image file
                    if not file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        continue
                    
                    # Check file age
                    file_age = now - os.path.getmtime(file_path)
                    if file_age > retention_seconds:
                        os.remove(file_path)
                        print(f"Removed old image: {file_path}")
            
            return True
        except Exception as e:
            print(f"Error cleaning up old images: {str(e)}")
            return False
    
    def get_storage_stats(self):
        """Get statistics about the image storage."""
        try:
            stats = {
                'total_images': 0,
                'storage_size_mb': 0,
                'entry_images': 0,
                'exit_images': 0,
                'blacklist_images': 0
            }
            
            # Count images in each directory
            for directory, counter in [
                (self.entry_dir, 'entry_images'),
                (self.exit_dir, 'exit_images'),
                (self.blacklist_dir, 'blacklist_images')
            ]:
                for _, _, files in os.walk(directory):
                    image_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                    stats[counter] = len(image_files)
                    stats['total_images'] += len(image_files)
                    
                    # Calculate storage size
                    dir_size = sum(os.path.getsize(os.path.join(directory, f)) for f in image_files)
                    stats['storage_size_mb'] += dir_size
            
            # Convert bytes to MB
            stats['storage_size_mb'] = round(stats['storage_size_mb'] / (1024 * 1024), 2)
            
            return stats
        except Exception as e:
            print(f"Error getting storage stats: {str(e)}")
            return None
    
    def delete_image(self, image_path):
        """Delete a specific image file."""
        try:
            if os.path.exists(image_path) and image_path.startswith(self.base_dir):
                os.remove(image_path)
                return True
            return False
        except Exception as e:
            print(f"Error deleting image {image_path}: {str(e)}")
            return False
    
    def clear_all_images(self):
        """Clear all stored images."""
        try:
            # Recreate directories instead of deleting individual files
            shutil.rmtree(self.base_dir)
            
            # Recreate the directory structure
            self._initialize()
            return True
        except Exception as e:
            print(f"Error clearing images: {str(e)}")
            return False 