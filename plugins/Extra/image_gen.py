import aiohttp
import os
from PIL import Image, ImageFilter, ImageOps, ImageDraw, ImageFont
from io import BytesIO
import asyncio

async def download_image(session, url):
    if not url:
        return None
    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.read()
                return Image.open(BytesIO(data))
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
    return None

async def generate_status_image(backdrop_url, poster_url, provider_urls, title, year, rating, genres, plot, is_upcoming=False, release_date=None):
    # Helper to clean text for PIL default font compatibility
    def clean_text_safe(text):
        if not text: return ""
        replacements = {
            "\u2018": "'", "\u2019": "'",
            "\u201c": '"', "\u201d": '"',
            "\u2013": "-", "\u2014": "-",
            "…": "...", "⭐": "*"
        }
        for k, v in replacements.items():
            text = str(text).replace(k, v)
        
        # If using default font, force Latin-1 or ASCII
        try:
            return text.encode('latin-1', 'ignore').decode('latin-1')
        except:
            return text.encode('ascii', 'ignore').decode('ascii')

    async with aiohttp.ClientSession() as session:
        # Download images
        backdrop_task = download_image(session, backdrop_url)
        poster_task = download_image(session, poster_url)
        
        provider_tasks = [download_image(session, url) for url in provider_urls[:5]] # limit to 5 logos
        
        results = await asyncio.gather(backdrop_task, poster_task, *provider_tasks)
        backdrop = results[0]
        poster = results[1]
        providers = results[2:]
        
        # Create Canvas
        width, height = 1280, 720
        canvas = Image.new("RGBA", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        # 1. Backdrop
        if backdrop:
            bg_w, bg_h = backdrop.size
            ratio = max(width/bg_w, height/bg_h)
            new_size = (int(bg_w*ratio), int(bg_h*ratio))
            backdrop = backdrop.resize(new_size, Image.Resampling.LANCZOS)
            
            left = (new_size[0] - width)/2
            top = (new_size[1] - height)/2
            backdrop = backdrop.crop((left, top, left+width, top+height))
            
            backdrop = backdrop.filter(ImageFilter.GaussianBlur(5))
            canvas.paste(backdrop, (0, 0))
            
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 160)) 
            canvas = Image.alpha_composite(canvas, overlay)
            draw = ImageDraw.Draw(canvas)
        else:
             canvas = Image.new("RGBA", (width, height), (20, 20, 20))
             draw = ImageDraw.Draw(canvas)

        # 2. Poster
        if poster:
            target_h = 600
            p_w, p_h = poster.size
            ratio = target_h / p_h
            new_p_w = int(p_w * ratio)
            poster = poster.resize((new_p_w, target_h), Image.Resampling.LANCZOS)
            
            shadow = Image.new("RGBA", (new_p_w + 20, target_h + 20), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle([(10, 10), (new_p_w+10, target_h+10)], radius=20, fill=(0, 0, 0, 150))
            shadow = shadow.filter(ImageFilter.GaussianBlur(10))
            
            pos_x = 60
            pos_y = (height - target_h) // 2
            
            canvas.paste(shadow, (pos_x - 5, pos_y - 5), shadow)

            mask = Image.new("L", (new_p_w, target_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([(0, 0), (new_p_w, target_h)], radius=20, fill=255)
            
            poster_rgba = poster.convert("RGBA")
            canvas.paste(poster_rgba, (pos_x, pos_y), mask)
            
            text_start_x = pos_x + new_p_w + 60
        else:
            text_start_x = 60

        # 3. Text Info
        # Font Loading Logic
        using_default = False
        try:
            # Reduced font sizes as requested
            title_font = ImageFont.truetype("arial.ttf", 43)
            meta_font = ImageFont.truetype("arial.ttf", 28)
            plot_font = ImageFont.truetype("arial.ttf", 24)
            genre_font = ImageFont.truetype("arial.ttf", 24)
            cs_font = ImageFont.truetype("arial.ttf", 55) # Larger for COMING SOON
        except IOError:
            try:
                # Try common Linux font
                title_font = ImageFont.truetype("DejaVuSans.ttf", 43)
                meta_font = ImageFont.truetype("DejaVuSans.ttf", 28)
                plot_font = ImageFont.truetype("DejaVuSans.ttf", 24)
                genre_font = ImageFont.truetype("DejaVuSans.ttf", 24)
                cs_font = ImageFont.truetype("DejaVuSans.ttf", 55)
            except IOError:
                title_font = ImageFont.load_default()
                meta_font = ImageFont.load_default()
                plot_font = ImageFont.load_default()
                genre_font = ImageFont.load_default()
                cs_font = ImageFont.load_default()
                using_default = True

        # Clean text if using default font or just generally to be safe from smart quotes
        if using_default:
            title = clean_text_safe(title)
            year = clean_text_safe(year)
            rating = clean_text_safe(rating)
            genres = clean_text_safe(genres)
            plot = clean_text_safe(plot)
            if release_date: release_date = clean_text_safe(release_date)
        else:
            replacements = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "…": "..."}
            for k, v in replacements.items():
                plot = str(plot).replace(k, v)
                title = str(title).replace(k, v)

        # Helper for wrapping text based on pixel width
        def wrap_text_pixel(draw, text, font, max_width):
            import textwrap
            try:
                avg_char_w = draw.textlength("a", font=font)
            except:
                try: 
                    bbox = draw.textbbox((0, 0), "a", font=font)
                    avg_char_w = bbox[2] - bbox[0]
                except: avg_char_w = 10
            
            if avg_char_w <= 0: avg_char_w = 10
            
            approx_chars = int(max_width / avg_char_w)
            lines = textwrap.wrap(str(text), width=approx_chars)
            # Make sure no line exceeds max_width strictly if possible (simple wrap might overshoot slightly with wide chars)
            return lines

        # Available width for text
        max_text_width = width - text_start_x - 40 # 40px right padding

        # Draw Text Content
        current_y = 100

        if is_upcoming:
            # Layout: Title (Year) \n\n COMING SOON \n Release Date
            
            # Title (Year)
            full_title = f"{title} ({year})"
            title_lines = wrap_text_pixel(draw, str(full_title), title_font, max_text_width)
            
            for line in title_lines[:3]: # Allow up to 3 lines
                draw.text((text_start_x, current_y), line, font=title_font, fill="white")
                current_y += 60
            
            current_y += 60 # Gap
            
            # COMING SOON
            draw.text((text_start_x, current_y), "COMING SOON", font=cs_font, fill="#FFD700") # Gold
            current_y += 80 
            
            # Release Date
            if release_date:
                draw.text((text_start_x, current_y), str(release_date), font=title_font, fill="white")

        else:
            # Standard Release Layout
            
            # Draw Title
            title_lines = wrap_text_pixel(draw, str(title), title_font, max_text_width)
            
            for line in title_lines[:2]: # Max 2 lines for title
                draw.text((text_start_x, current_y), line, font=title_font, fill="white")
                current_y += 60 # Reduced spacing

            current_y += 10 # Spacer
            
            # Draw Meta
            meta_text = f"{year}   |   Rat: {rating}"
            draw.text((text_start_x, current_y), meta_text, font=meta_font, fill="#FFD700")
            current_y += 50 # Reduced spacing
            
            if genres:
                 draw.text((text_start_x, current_y), str(genres), font=genre_font, fill="#A0A0A0")
                 current_y += 50 # Reduced spacing

            # Divider
            draw.line([(text_start_x, current_y), (text_start_x + min(300, max_text_width), current_y)], fill="white", width=2)
            current_y += 35 # Reduced spacing

            # Draw Plot
            plot = str(plot) if plot else "No description available."
            plot_lines = wrap_text_pixel(draw, plot, plot_font, max_text_width)
            
            for line in plot_lines[:7]: # Max 7 lines for plot
                draw.text((text_start_x, current_y), line, font=plot_font, fill="white")
                current_y += 35 # Reduced spacing

        # 4. Provider Logos
        if providers:
            providers = [p for p in providers if p]
            if providers:
                logo_size = 70
                padding = 20
                
                resized_providers = []
                for p in providers:
                    pw, ph = p.size
                    ratio = logo_size / ph
                    new_pw = int(pw * ratio)
                    p_resized = p.resize((new_pw, logo_size), Image.Resampling.LANCZOS)
                    resized_providers.append(p_resized)
                
                current_x = width - 60
                bottom_y = height - 60 - logo_size
                
                for p in reversed(resized_providers):
                    current_x -= p.width
                    canvas.paste(p, (current_x, bottom_y), p if p.mode == 'RGBA' else None)
                    current_x -= padding

        # 5. Watermark (Logo + Text)
        try:
            # Assume file is at plugins/Extra/logo.jpg relative to cwd
            logo_path = "plugins/Extra/logo.jpg"
            if os.path.exists(logo_path):
                logo_img = Image.open(logo_path).convert("RGBA")
                
                # Resize logo (Height reduced to 50px)
                target_logo_h = 50
                l_w, l_h = logo_img.size
                ratio = target_logo_h / l_h
                new_l_w = int(l_w * ratio)
                logo_img = logo_img.resize((new_l_w, target_logo_h), Image.Resampling.LANCZOS)
                
                # Apply Rounded Corners Mask
                mask = Image.new("L", (new_l_w, target_logo_h), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle([(0, 0), (new_l_w, target_logo_h)], radius=15, fill=255)
                # Apply mask to alpha channel ensuring existing alpha is respected if any (start new or composite)
                # Since input is jpg converted to rgba, it's fully opaque. We can just set alpha.
                logo_img.putalpha(mask)

                # Position: Top Right
                w_x = width - new_l_w - 40
                w_y = 40
                
                canvas.paste(logo_img, (w_x, w_y), logo_img)
                
                # Text
                wm_text = "t.me/moovidex"
                
                # Create smaller font for watermark
                try:
                    wm_font = ImageFont.truetype("arial.ttf", 20)
                except IOError:
                    try:
                        wm_font = ImageFont.truetype("DejaVuSans.ttf", 20)
                    except:
                        wm_font = ImageFont.load_default()

                # Calculate text size to center below logo
                try:
                    bbox = draw.textbbox((0, 0), wm_text, font=wm_font)
                    text_w = bbox[2] - bbox[0]
                    text_h = bbox[3] - bbox[1]
                except:
                    text_w = draw.textlength(wm_text, font=wm_font)
                    text_h = 20 # approx

                text_x = w_x + (new_l_w - text_w) // 2
                
                # Boundary check - ensure text doesn't go off screen right
                if text_x + text_w > width - 10:
                     text_x = width - text_w - 10
                     
                text_y = w_y + target_logo_h + 5
                
                # Add shadow/stroke for visibility
                draw.text((text_x+1, text_y+1), wm_text, font=wm_font, fill="black")
                draw.text((text_x, text_y), wm_text, font=wm_font, fill="white")
        except Exception as e:
            print(f"Error adding watermark: {e}")
                    
        out_io = BytesIO()
        canvas = canvas.convert("RGB")
        canvas.save(out_io, 'JPEG', quality=95)
        out_io.seek(0)
        return out_io
