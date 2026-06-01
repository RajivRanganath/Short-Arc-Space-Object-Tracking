import requests
import os

def download_fengyun_data():
    # UPDATED: Use INTDES (International Designator) instead of GROUP
    # 1999-025 is the launch ID for Fengyun-1C
    url = "https://celestrak.org/NORAD/elements/gp.php?INTDES=1999-025&FORMAT=tle"
    save_path = "data/fengyun_1c.txt"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }

    print("⬇️  Downloading Fengyun-1C debris data (ID: 1999-025)...")
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            content = response.text
            line_count = len(content.splitlines())
            
            if "No GP data found" in content or line_count < 3:
                print(f"⚠️  Warning: API returned error. Content:\n{content[:100]}")
                return

            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, "w") as f:
                f.write(content)
            
            # 3 lines per TLE
            obj_count = line_count // 3
            print(f"✅ Success! Saved to {save_path}")
            print(f"📊 Total objects retrieved: {obj_count}")
        else:
            print(f"❌ Failed. HTTP Status: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    download_fengyun_data()
