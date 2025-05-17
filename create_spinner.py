from PIL import Image, ImageDraw
import os

# Create directory if it doesn't exist
os.makedirs('app/resources', exist_ok=True)

# Configuration
width, height = 64, 64
center = width // 2
radius = 20
dot_radius = 4
frames = 8
background_color = (255, 255, 255, 0)  # Transparent background
spinner_color = (59, 175, 218)  # #3bafda

# Create frames
images = []

for i in range(frames):
    # Create a transparent image
    img = Image.new('RGBA', (width, height), background_color)
    draw = ImageDraw.Draw(img)
    
    # Calculate angle for this frame
    angle = i * (360 / frames)
    
    # Calculate position for the highlighted dot
    x = center + int(radius * (angle / 360) * 2 * 3.14159)
    y = center + int(radius * (angle / 360) * 2 * 3.14159)
    
    # Draw spinner (circle with one section highlighted)
    for j in range(frames):
        dot_angle = j * (360 / frames)
        dot_x = center + int(radius * (dot_angle / 360) * 2 * 3.14159)
        dot_y = center + int(radius * (dot_angle / 360) * 2 * 3.14159)
        
        # Get the dot color (highlight current position)
        if j == i:
            dot_color = spinner_color
        else:
            r, g, b = spinner_color
            # Fade other dots
            dot_color = (r, g, b, 128)
        
        # Draw the dot
        draw.ellipse(
            [center + radius * round(2*j/frames - 1), center - dot_radius,
             center + radius * round(2*j/frames - 1) + 2*dot_radius, center + dot_radius],
            fill=dot_color
        )
    
    images.append(img)

# Save the animation
images[0].save(
    'app/resources/loading_spinner.gif',
    save_all=True,
    append_images=images[1:],
    optimize=False,
    duration=100,  # milliseconds per frame
    loop=0  # infinite loop
)

print("Spinner GIF created successfully at app/resources/loading_spinner.gif") 