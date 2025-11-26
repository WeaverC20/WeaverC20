import os
import requests
import random

# CONFIGURATION
USERNAME = os.getenv('USERNAME')
TOKEN = os.getenv('GH_TOKEN') # Requires a PAT to fetch detailed contribution data
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
        raise Exception(f"Query failed: {response.status_code}")
    
    return response.json()['data']['user']['contributionsCollection']['contributionCalendar']['weeks']

def generate_svg(weeks):
    # CSS Styles for the animation
    # We define a "diffusion" animation that moves from left to target
    css = """
    <style>
        .box { animation-timing-function: cubic-bezier(0.25, 1, 0.5, 1); animation-fill-mode: forwards; }
        @keyframes diffuse {
            0% { transform: translate(-800px, var(--rand-y)); opacity: 0; }
            20% { opacity: 1; }
            50% { transform: translate(var(--mid-x), var(--mid-y)); }
            100% { transform: translate(0, 0); }
        }
    </style>
    """

    rects = []
    
    for w_idx, week in enumerate(weeks):
        for day in week['contributionDays']:
            if day['contributionLevel'] == "NONE":
                continue # Skip empty days to emphasize the "particles"
            
            color = COLORS.get(day['contributionLevel'], "#161b22")
            
            # Final Destination
            x = w_idx * 14 + 10
            y = day['weekday'] * 14 + 30
            
            # Animation Variables
            # We give every particle a random bounce path
            mid_x = random.randint(-200, x) # Random midway point
            mid_y = random.randint(-50, 200) # Random midway height
            rand_start_y = random.randint(-100, 300) # Start at random height on the left
            
            duration = random.uniform(2.0, 4.0) # Different speeds for gas effect
            delay = random.uniform(0, 1.5) # Don't all start at once
            
            rect = f"""
            <rect x="{x}" y="{y}" width="10" height="10" rx="2" fill="{color}" class="box"
                style="
                    --mid-x: {mid_x - x}px;
                    --mid-y: {mid_y - y}px;
                    --rand-y: {rand_start_y - y}px;
                    animation-name: diffuse;
                    animation-duration: {duration}s;
                    animation-delay: {delay}s;
                "
            />
            """
            rects.append(rect)

    svg_content = f"""
    <svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#0d1117" rx="6" /> {css}
        <g>{''.join(rects)}</g>
        <text x="15" y="20" fill="#c9d1d9" font-family="monospace" font-size="14">Contribution Diffusion</text>
    </svg>
    """
    
    return svg_content

def main():
    if not USERNAME or not TOKEN:
        print("Error: USERNAME or GH_TOKEN environment variables missing.")
        return

    try:
        weeks = fetch_contributions(USERNAME, TOKEN)
        svg = generate_svg(weeks)
        
        with open("diffusion_graph.svg", "w") as f:
            f.write(svg)
        print("Generated diffusion_graph.svg")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()