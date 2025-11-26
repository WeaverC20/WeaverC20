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
    css_keyframes = []
    rects = []
    
    # Generate static grid background
    background_grid = []
    for c in range(GRID_COLS):
        for r in range(GRID_ROWS):
            bg_x = c * RECT_SPACING + CHART_OFFSET_X
            bg_y = r * RECT_SPACING + CHART_OFFSET_Y
            # Note: We use x and y attributes for the static background grid
            background_grid.append(f'<rect x="{bg_x}" y="{bg_y}" width="{RECT_SIZE}" height="{RECT_SIZE}" rx="2" fill="{COLORS["NONE"]}" opacity="0.1"/>')


    for w_idx, week in enumerate(weeks):
        for day in week['contributionDays']:
            if day['contributionLevel'] == "NONE":
                continue # Only animate contributed days
            
            color = COLORS.get(day['contributionLevel'], "#161b22")
            
            # 1. Final Destination (Grid Coords)
            final_col = w_idx
            final_row = day['weekday']
            
            # 2. Initial Position (Grid Coords) - Start on the far left (col 0)
            current_col = 0
            current_row = random.randint(0, GRID_ROWS - 1)
            
            # 3. Final & Initial Pixel Coords (for keyframes)
            final_x_px = final_col * RECT_SPACING + CHART_OFFSET_X
            final_y_px = final_row * RECT_SPACING + CHART_OFFSET_Y
            initial_x_px = current_col * RECT_SPACING + CHART_OFFSET_X
            initial_y_px = current_row * RECT_SPACING + CHART_OFFSET_Y
            
            # --- Keyframe Generation Setup ---
            # Unique name for each keyframe animation
            keyframe_name = f"diffuse-{w_idx}-{day['weekday']}-{random.randint(0,9999)}"
            
            keyframes_str = f"@{keyframe_name} {{"
            # 0% Keyframe: Start inside the chart boundaries
            # Opacity starts at 0.8 for a 'pop-in' effect
            keyframes_str += f"0% {{ transform: translate({initial_x_px}px, {initial_y_px}px); opacity: 0.8; }}"

            # Calculate total distance and animation parameters
            total_cols_to_move = final_col - 0 # Starting at col 0
            
            # Optimized Duration: Shorter base time + factor of distance
            base_duration = 3.0 
            distance_factor = 0.3 * total_cols_to_move 
            animation_duration = base_duration + distance_factor + random.uniform(0.5, 2.0) 
            
            # *** CRITICAL FIX: Drastically reducing the number of hops (keyframes) ***
            # Aim for 5 to 10 hops maximum to prevent file truncation
            num_hops = max(5, int(total_cols_to_move * 0.2) + random.randint(1, 5))
            
            # --- Biased Random Walk Simulation (Generating the intermediate hops) ---
            for i in range(1, num_hops):
                
                # JUMP CONSTRAINT: Max 3 squares away per hop
                max_jump = 3
                
                col_diff = final_col - current_col
                
                # Biasing logic to push the particle towards its final column
                if col_diff > 10:
                    # Far away: Strong bias right 
                    col_move_options = [1, 2, 3, 0, -1] 
                elif col_diff > 0:
                    # Close but not there: Slight bias right 
                    col_move_options = [1, 0, -1] 
                else:
                    # Already at or past target: Pure random walk around the final column
                    col_move_options = [-1, 0, 1] 
                    
                col_jump = random.choice(col_move_options)
                row_jump = random.randint(-max_jump, max_jump)

                # Clamp jump magnitude
                col_jump = max(-max_jump, min(col_jump, max_jump)) 
                
                # Calculate next grid coordinates
                next_col = current_col + col_jump
                next_row = current_row + row_jump
                
                # BOUNDARY CHECK: Ensure it stays within the chart
                next_col = max(0, min(next_col, GRID_COLS - 1))
                next_row = max(0, min(next_row, GRID_ROWS - 1))
                
                # Update current position for next iteration
                current_col = next_col
                current_row = next_row
                
                # Convert grid coordinates to pixel coordinates
                hop_x_px = next_col * RECT_SPACING + CHART_OFFSET_X
                hop_y_px = next_row * RECT_SPACING + CHART_OFFSET_Y
                
                # Calculate keyframe percentage based on hop number
                # We stop slightly early (99%) to allow the final 100% position to snap correctly
                keyframe_percent = int((i / num_hops) * 99) 
                keyframes_str += f"{keyframe_percent}% {{ transform: translate({hop_x_px}px, {hop_y_px}px); opacity: 1; }}"

            # 100% Keyframe: Snap to the final, actual contribution spot
            keyframes_str += f"100% {{ transform: translate({final_x_px}px, {final_y_px}px); opacity: 1; }}"
            keyframes_str += "}"
            css_keyframes.append(keyframes_str)

            # Assign animation to the rect
            delay = random.uniform(0, 3.0) 
            
            rect = f"""
            <rect width="{RECT_SIZE}" height="{RECT_SIZE}" rx="2" fill="{color}" class="box"
                style="
                    /* CRITICAL: No x/y attributes. Position is ONLY controlled by CSS transform. */
                    animation-name: {keyframe_name};
                    animation-duration: {animation_duration}s;
                    animation-delay: {delay}s;
                    animation-fill-mode: forwards;
                    animation-timing-function: linear;
                "
            />
            """
            # CRITICAL FIX: Append the rectangle to the list!
            rects.append(rect)


    combined_css = "\n".join(css_keyframes)
    # Define a default style for all boxes
    full_css_style = f"<style>.box {{ animation-timing-function: linear; animation-fill-mode: forwards; }} {combined_css}</style>"

    # Assemble the final SVG
    svg_content = f"""
    <svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#0d1117" rx="6" />
        <text x="15" y="20" fill="#c9d1d9" font-family="monospace" font-size="14">Contribution Diffusion</text>
        <g>
            {''.join(background_grid)}
            {full_css_style}
            {''.join(rects)}
        </g>
    </svg>
    """
    
    return svg_content

def main():
    # Check for required environment variables
    # Note: These variables are loaded from the .env file via load_dotenv()
    if not USERNAME or not TOKEN:
        print(f"Error: GH_USERNAME or GH_TOKEN is missing. Ensure your .env file is correct.")
        # Exit gracefully if environment variables are missing
        sys.exit(1)

    print(f"Fetching data for user: {USERNAME}")

    try:
        weeks = fetch_contributions(USERNAME, TOKEN)
        if not weeks:
            print("No contribution data found or permission error. Generating fallback graph.")
            # Fallback SVG in case of API failure
            svg = f"""<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="#0d1117" rx="6" /><text x="15" y="20" fill="#c9d1d9" font-family="monospace" font-size="14">No Contribution Data (Check Token/Permissions)</text></svg>"""
        else:
            svg = generate_svg(weeks)
        
        with open("diffusion_graph.svg", "w") as f:
            f.write(svg)
        print("Generated diffusion_graph.svg successfully")
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()