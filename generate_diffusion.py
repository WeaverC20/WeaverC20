import os
import requests
import random
import sys

# CONFIGURATION
USERNAME = os.getenv('GH_USERNAME')
TOKEN = os.getenv('GH_TOKEN') 

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
CHART_OFFSET_Y = 30 # For title

# Define the boundaries of the grid
GRID_COLS = 53 # Approx 53 weeks
GRID_ROWS = 7  # 7 days a week

def fetch_contributions(username, token):
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
        raise Exception(f"Query failed: {response.status_code}")
    
    data = response.json()
    if 'errors' in data:
        print(f"GraphQL Error: {data['errors']}")
        return []
        
    return data['data']['user']['contributionsCollection']['contributionCalendar']['weeks']

def generate_svg(weeks):
    # CSS Styles for the animation
    css_keyframes = []
    rects = []
    
    # Generate static grid background 
    background_grid = []
    for c in range(GRID_COLS):
        for r in range(GRID_ROWS):
            bg_x = c * RECT_SPACING + CHART_OFFSET_X
            bg_y = r * RECT_SPACING + CHART_OFFSET_Y
            background_grid.append(f'<rect x="{bg_x}" y="{bg_y}" width="{RECT_SIZE}" height="{RECT_SIZE}" rx="2" fill="{COLORS["NONE"]}" opacity="0.1"/>')


    for w_idx, week in enumerate(weeks):
        for day in week['contributionDays']:
            if day['contributionLevel'] == "NONE":
                continue # Only animate contributed days
            
            color = COLORS.get(day['contributionLevel'], "#161b22")
            
            # 1. Final Destination (Grid Coords)
            final_col = w_idx
            final_row = day['weekday']
            
            # 2. Initial Position (Grid Coords)
            current_col = 0
            current_row = random.randint(0, GRID_ROWS - 1)
            
            # 3. Final & Initial Pixel Coords (for keyframes)
            final_x_px = final_col * RECT_SPACING + CHART_OFFSET_X
            final_y_px = final_row * RECT_SPACING + CHART_OFFSET_Y
            initial_x_px = current_col * RECT_SPACING + CHART_OFFSET_X
            initial_y_px = current_row * RECT_SPACING + CHART_OFFSET_Y
            
            # --- Keyframe Generation ---
            keyframe_name = f"diffuse-{w_idx}-{day['weekday']}-{random.randint(0,999)}"
            
            keyframes_str = f"@{keyframe_name} {{"
            # 0% Keyframe: Start inside the chart boundaries
            keyframes_str += f"0% {{ transform: translate({initial_x_px}px, {initial_y_px}px); opacity: 0.8; }}"

            # Calculate total duration and number of steps for slow fill
            total_cols_to_move = final_col - current_col
            
            # Use shorter paths and duration to reduce file size:
            base_duration = 5.0 # Reduced base time for shorter animations
            distance_factor = 0.5 * total_cols_to_move 
            # Smaller random range for duration
            animation_duration = base_duration + distance_factor + random.uniform(1.0, 3.0) 
            
            # *** CRITICAL FIX: Drastically reducing the number of hops ***
            # Aim for 5 to 16 hops maximum per particle instead of 10 to 40+
            num_hops = max(5, int(total_cols_to_move * 0.5) + random.randint(3, 8))
            
            # --- Biased Random Walk Simulation (Generating the intermediate hops) ---
            for i in range(1, num_hops):
                
                # JUMP CONSTRAINT: Max 3 squares away
                max_jump = 3
                
                col_diff = final_col - current_col
                
                # BIAS TO THE RIGHT: Increase probability of positive jump if far left
                if col_diff > 10:
                    # Far away: Strong bias right (3 right, 1 stay, 1 left)
                    col_move_options = [1, 2, 3, 0, -1] 
                elif col_diff > 0:
                    # Close but not there: Slight bias right (1 right, 1 stay, 1 left)
                    col_move_options = [1, 0, -1] 
                else:
                    # Already at or past target: Pure random walk
                    col_move_options = [-1, 0, 1] 
                    
                col_jump = random.choice(col_move_options)
                row_jump = random.randint(-max_jump, max_jump)

                # Clamp jump magnitude to max_jump
                col_jump = max(-max_jump, min(col_jump, max_jump)) 
                
                # Calculate next grid coordinates
                next_col = current_col + col_jump
                next_row = current_row + row_jump
                
                # BOUNDARY CHECK 2: Ensure it stays within the chart (0 to GRID_COLS-1)
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
            delay = random.uniform(0, 3.0) # Increased initial delay variance
            
            rect = f"""
            <rect width="{RECT_SIZE}" height="{RECT_SIZE}" rx="2" fill="{color}" class="box"
                style="
                    transform: translate({initial_x_px}px, {initial_y_px}px); /* Initial position set here */
                    animation-name: {keyframe_name};
                    animation-duration: {animation_duration}s;
                    animation-delay: {delay}s;
                    animation-fill-mode: forwards;
                    animation-timing-function: linear; /* Linear timing gives steady movement between hops */
                "
            />
            """
            rects.append(rect)

    combined_css = "\n".join(css_keyframes)
    full_css_style = f"<style>.box {{ animation-timing-function: linear; animation-fill-mode: forwards; }} {combined_css}</style>"

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
    if not USERNAME or not TOKEN:
        print(f"Error: {'GH_USERNAME' if not USERNAME else 'GH_TOKEN'} is missing.")
        sys.exit(1)

    print(f"Fetching data for user: {USERNAME}")

    try:
        weeks = fetch_contributions(USERNAME, TOKEN)
        if not weeks:
            print("No contribution data found or permission error. Generating fallback graph.")
            svg = f"""<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="#0d1117" rx="6" /><text x="15" y="20" fill="#c9d1d9" font-family="monospace" font-size="14">No Contribution Data (Check Token/Permissions)</text></svg>"""
        else:
            svg = generate_svg(weeks)
        
        with open("diffusion_graph.svg", "w") as f:
            f.write(svg)
        print("Generated diffusion_graph.svg successfully")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()