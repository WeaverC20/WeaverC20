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

# New: Define the boundaries of the grid for random movement
GRID_COLS = 53 # Approx 53 weeks in a year
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
                date # Added date to ensure we get a full year
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
        # Fallback for errors: return an empty list or handle gracefully
        return []
        
    return data['data']['user']['contributionsCollection']['contributionCalendar']['weeks']

def generate_svg(weeks):
    # CSS Styles for the animation
    css_keyframes = []
    rects = []
    
    # Generate static grid background (optional, for reference)
    background_grid = []
    for c in range(GRID_COLS):
        for r in range(GRID_ROWS):
            bg_x = c * RECT_SPACING + CHART_OFFSET_X
            bg_y = r * RECT_SPACING + CHART_OFFSET_Y
            background_grid.append(f'<rect x="{bg_x}" y="{bg_y}" width="{RECT_SIZE}" height="{RECT_SIZE}" rx="2" fill="{COLORS["NONE"]}" opacity="0.5"/>')


    for w_idx, week in enumerate(weeks):
        for day in week['contributionDays']:
            if day['contributionLevel'] == "NONE":
                continue # Only animate contributed days
            
            color = COLORS.get(day['contributionLevel'], "#161b22")
            
            # Final Destination (relative to its own starting point 0,0)
            final_x = w_idx * RECT_SPACING + CHART_OFFSET_X
            final_y = day['weekday'] * RECT_SPACING + CHART_OFFSET_Y
            
            # New: Initial Position - all start in the leftmost column randomly
            start_col = 0
            start_row = random.randint(0, GRID_ROWS - 1)
            initial_x = start_col * RECT_SPACING + CHART_OFFSET_X
            initial_y = start_row * RECT_SPACING + CHART_OFFSET_Y
            
            # --- Generate Keyframes for each particle's unique hop path ---
            keyframe_name = f"diffuse-{w_idx}-{day['weekday']}-{random.randint(0,999)}"
            
            keyframes_str = f"@{keyframe_name} {{"
            keyframes_str += f"0% {{ transform: translate({initial_x}px, {initial_y}px); opacity: 0.8; }}"

            num_hops = random.randint(3, 8) # More hops for more random motion
            
            # Calculate total animation duration based on path length and desired speed
            # The more "right" the target, the longer it should take
            base_duration = 2.0 # Minimum duration for simple hops
            max_right_duration_factor = 0.05 * w_idx # Slower diffusion to the right
            animation_duration = base_duration + max_right_duration_factor + random.uniform(0.5, 1.5) # Add some randomness
            
            # Generate intermediate hop positions
            for i in range(1, num_hops):
                progress = i / num_hops # Percentage of animation completed
                
                # Slower rightward progression: bias x towards the left initially
                # Use a non-linear progression for X
                target_x_progress = (progress ** 1.5) # x advances slower at the start
                current_x_target = initial_x + target_x_progress * (final_x - initial_x)
                
                # Add significant random jitter around the intended path
                jitter_x = random.randint(-RECT_SPACING * 2, RECT_SPACING * 2) 
                jitter_y = random.randint(-RECT_SPACING * 2, RECT_SPACING * 2)
                
                # Ensure hops stay somewhat within the grid bounds
                hop_x = max(CHART_OFFSET_X, min(current_x_target + jitter_x, CHART_OFFSET_X + (GRID_COLS-1) * RECT_SPACING))
                hop_y = max(CHART_OFFSET_Y, min(initial_y + progress * (final_y - initial_y) + jitter_y, CHART_OFFSET_Y + (GRID_ROWS-1) * RECT_SPACING))
                
                keyframe_percent = int(progress * 100 * 0.9) # End before 100% to allow final destination
                keyframes_str += f"{keyframe_percent}% {{ transform: translate({hop_x}px, {hop_y}px); opacity: 1; }}"

            keyframes_str += f"100% {{ transform: translate({final_x}px, {final_y}px); opacity: 1; }}"
            keyframes_str += "}"
            css_keyframes.append(keyframes_str)

            # Assign animation to the rect
            delay = random.uniform(0, 1.5) # Don't all start at once
            
            rect = f"""
            <rect width="{RECT_SIZE}" height="{RECT_SIZE}" rx="2" fill="{color}" class="box"
                style="
                    transform: translate({initial_x}px, {initial_y}px); /* Initial position set here */
                    animation-name: {keyframe_name};
                    animation-duration: {animation_duration}s;
                    animation-delay: {delay}s;
                    animation-fill-mode: forwards;
                    animation-timing-function: ease-in-out; /* Smoother hops */
                "
            />
            """
            rects.append(rect)

    # Combine all styles and rects
    combined_css = "\n".join(css_keyframes)
    full_css_style = f"<style>.box {{ animation-timing-function: ease-in-out; animation-fill-mode: forwards; }} {combined_css}</style>"

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
    if not USERNAME:
        print("Error: GH_USERNAME is missing.")
        sys.exit(1)
    if not TOKEN:
        print("Error: GH_TOKEN is missing. Please check Repository Secrets.")
        sys.exit(1)

    print(f"Fetching data for user: {USERNAME}")

    try:
        weeks = fetch_contributions(USERNAME, TOKEN)
        if not weeks:
            print("No contribution data found or permission error. Generating empty graph.")
            # Optionally generate a fallback empty graph
            svg = f"""
            <svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg">
                <rect width="100%" height="100%" fill="#0d1117" rx="6" />
                <text x="15" y="20" fill="#c9d1d9" font-family="monospace" font-size="14">No Contribution Data (Check Token/Permissions)</text>
            </svg>
            """
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