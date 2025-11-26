import os
import requests
import random
import sys
# New import to load .env file variables
from dotenv import load_dotenv

# CONFIGURATION
# 1. Load environment variables from the .env file (if it exists)
load_dotenv() 

# 2. Assign variables using os.getenv(), which pulls from the .env file now.
USERNAME = os.getenv('GH_USERNAME')
TOKEN = os.getenv('GH_TOKEN') 

# Colors (Dark mode style: Less -> More contributions)
COLORS = {
    "NONE": "#161b22",
    "FIRST_QUARTILE": "#0e4429",
    "SECOND_QUARTILE": "#006d32",
    "THIRD_QUARTILE": "#26a641",
    "FOURTH_QUARTILE": "#39d353"
}
WIDTH = 850
HEIGHT = 200
RECT_SIZE = 10
RECT_SPACING = 14 # Space between centers of squares (10px rect + 4px gap)
CHART_OFFSET_X = 10
CHART_OFFSET_Y = 30 # Y offset for title/margin

# Define the boundaries of the grid
GRID_COLS = 53 # Approx 53 weeks
GRID_ROWS = 7  # 7 days a week (0 is Sunday)

def fetch_contributions(username, token):
    """Fetches contribution data from the GitHub GraphQL API."""
    headers = {"Authorization": f"Bearer {token}"}
    query = """
    query($userName:String!) {
      user(login: $userName){
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                contributionLevel
                weekday
              }
            }
          }
        }
      }
    }
    """
    variables = {"userName": username}
    response = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': variables}, headers=headers)
    
    if response.status_code != 200:
        print(f"API Error: {response.text}")
        raise Exception(f"Query failed with status code: {response.status_code}")
    
    data = response.json()
    if 'errors' in data:
        # Handle cases where the token is invalid or username is not found
        print(f"GraphQL Error: {data['errors']}")
        return []
        
    return data['data']['user']['contributionsCollection']['contributionCalendar']['weeks']

def generate_svg(weeks):
    """Generates the SVG content with animated contribution rectangles."""
    rects = []
    
    # Generate static grid background
    background_grid = []
    for c in range(GRID_COLS):
        for r in range(GRID_ROWS):
            bg_x = c * RECT_SPACING + CHART_OFFSET_X
            bg_y = r * RECT_SPACING + CHART_OFFSET_Y
            # Background grid visibility remains 0.3
            background_grid.append(f'<rect x="{bg_x}" y="{bg_y}" width="{RECT_SIZE}" height="{RECT_SIZE}" rx="2" fill="{COLORS["NONE"]}" opacity="0.3"/>')

    animated_squares_count = 0

    for w_idx, week in enumerate(weeks):
        for day in week['contributionDays']:
            if day['contributionLevel'] == "NONE":
                continue # Only animate contributed days
            
            color = COLORS.get(day['contributionLevel'], "#161b22")
            
            # Final position set by x and y attributes
            final_x_px = w_idx * RECT_SPACING + CHART_OFFSET_X
            final_y_px = day['weekday'] * RECT_SPACING + CHART_OFFSET_Y
            
            # --- Animation Variables (Passed via CSS Custom Properties) ---
            
            # Start position offset (relative to final position)
            # Starting on the far left, slightly offset vertically
            start_x_offset = -final_x_px - random.randint(10, 50) 
            start_y_offset = random.randint(-50, 50) 
            
            # Duration and Delay
            animation_duration = random.uniform(2.5, 5.0) 
            delay = random.uniform(0, 3.0) 
            
            rect = f"""
            <rect x="{final_x_px}" y="{final_y_px}" width="{RECT_SIZE}" height="{RECT_SIZE}" rx="2" fill="{color}" class="box"
                style="
                    /* Pass unique starting offsets to the shared keyframe via CSS variables */
                    --start-x: {start_x_offset}px; 
                    --start-y: {start_y_offset}px; 

                    /* Animation styles */
                    animation-name: diffuse-motion; /* All boxes use the same keyframe */
                    animation-duration: {animation_duration}s;
                    animation-delay: {delay}s;
                    animation-fill-mode: forwards;
                    animation-timing-function: cubic-bezier(0.2, 0.8, 0.2, 1); /* Smoother animation curve */
                    animation-iteration-count: infinite; /* Set to infinite for visible testing */
                "
            />
            """
            rects.append(rect)
            animated_squares_count += 1

    # --- SINGLE, SHARED KEYFRAME DEFINITION ---
    shared_keyframe = """
    @keyframes diffuse-motion {
        /* Start position is defined by the unique CSS variables --start-x and --start-y */
        0% { transform: translate(var(--start-x), var(--start-y)); opacity: 0; }
        50% { opacity: 1; }
        /* End position is (0, 0) relative to the rect's static x/y attributes */
        100% { transform: translate(0, 0); opacity: 1; }
    }
    """
    
    # Define a default style for all boxes, wrapped in CDATA for robust XML parsing
    full_css_style = f"""
    <style type="text/css">
    <![CDATA[
    .box {{ 
        animation-fill-mode: forwards; 
        /* Important for SVG: ensures transforms are relative to the element */
        transform-box: fill-box; 
        transform-origin: center;
    }}
    {shared_keyframe}
    ]]>
    </style>
    """

    # Assemble the final SVG 
    svg_content = f"""
    <svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#0d1117" rx="6" />
        <text x="15" y="20" fill="#c9d1d9" font-family="monospace" font-size="14">Contribution Diffusion for {USERNAME}</text>
        {full_css_style}
        <g>
            {''.join(background_grid)}
            {''.join(rects)}
        </g>
    </svg>
    """
    
    # Return the SVG content and the count of animated squares for debugging
    return svg_content, animated_squares_count

def main():
    # Diagnostic Print 1: Check if credentials loaded
    print(f"DEBUG: Credentials Loaded - Username: {USERNAME} | Token Check: {'Success' if TOKEN else 'FAIL'}")

    if not USERNAME or not TOKEN:
        print(f"Error: GH_USERNAME or GH_TOKEN is missing. Ensure your .env file is correct.")
        sys.exit(1)

    print(f"Fetching data for user: {USERNAME}")

    try:
        weeks = fetch_contributions(USERNAME, TOKEN)
        
        # Diagnostic Print 2: Check data integrity
        print(f"DEBUG: Fetched {len(weeks)} weeks of data.")

        if not weeks:
            print("No contribution data found or permission error. Generating fallback graph.")
            svg = f"""<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="#0d1117" rx="6" /><text x="15" y="20" fill="#c9d1d9" font-family="monospace" font-size="14">No Contribution Data (Check Token/Permissions)</text></svg>"""
        else:
            svg, animated_squares_count = generate_svg(weeks)
            # Diagnostic Print 3: Check generated content
            print(f"DEBUG: Generated {animated_squares_count} animated squares.")
            
        
        with open("diffusion_graph.svg", "w") as f:
            f.write(svg)

        # Diagnostic Print 4: Check file size
        svg_size_kb = len(svg.encode('utf-8')) / 1024
        print(f"DEBUG: SVG file size: {svg_size_kb:.2f} KB.")
        print("Generated diffusion_graph.svg successfully")

        # CRITICAL VIEWING INSTRUCTION
        print("\n*** IMPORTANT: How to view the animation ***")
        print("1. Open the generated 'diffusion_graph.svg' file.")
        print("2. You MUST view it in a modern WEB BROWSER (Chrome, Firefox, Safari).")
        print("3. Image viewers often do NOT support CSS animations.")
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()