import aiohttp
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

async def generate_status_image(backdrop_url, poster_url, provider_urls, title, year, rating, genres, plot):
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
            # Resize backdrop to cover
            bg_w, bg_h = backdrop.size
            ratio = max(width/bg_w, height/bg_h)
            new_size = (int(bg_w*ratio), int(bg_h*ratio))
            backdrop = backdrop.resize(new_size, Image.Resampling.LANCZOS)
            
            # Crop center
            left = (new_size[0] - width)/2
            top = (new_size[1] - height)/2
            backdrop = backdrop.crop((left, top, left+width, top+height))
            
            # Apply blur
            backdrop = backdrop.filter(ImageFilter.GaussianBlur(5))
            
            # Paste backdrop
            canvas.paste(backdrop, (0, 0))
            
            # Add darken overlay
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 160)) # Darker overlay for text readability
            canvas = Image.alpha_composite(canvas, overlay)
        else:
             # Fallback background
             canvas = Image.new("RGBA", (width, height), (20, 20, 20))
             draw = ImageDraw.Draw(canvas)

        # 2. Poster with Shadow and Radius
        if poster:
            target_h = 600
            p_w, p_h = poster.size
            ratio = target_h / p_h
            new_p_w = int(p_w * ratio)
            poster = poster.resize((new_p_w, target_h), Image.Resampling.LANCZOS)
            
            # Shadow
            shadow = Image.new("RGBA", (new_p_w + 20, target_h + 20), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle([(10, 10), (new_p_w+10, target_h+10)], radius=20, fill=(0, 0, 0, 150))
            shadow = shadow.filter(ImageFilter.GaussianBlur(10))
            
            pos_x = 60
            pos_y = (height - target_h) // 2
            
            canvas.paste(shadow, (pos_x - 5, pos_y - 5), shadow)

            # Rounded Poster
            mask = Image.new("L", (new_p_w, target_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([(0, 0), (new_p_w, target_h)], radius=20, fill=255)
            
            poster_rgba = poster.convert("RGBA")
            
            canvas.paste(poster_rgba, (pos_x, pos_y), mask)
            
            text_start_x = pos_x + new_p_w + 60
        else:
            text_start_x = 60

        # 3. Text Info
        text_width = width - text_start_x - 60
        
        try:
            # Try loading Arial
            title_font = ImageFont.truetype("arial.ttf", 60)
            meta_font = ImageFont.truetype("arial.ttf", 35)
            plot_font = ImageFont.truetype("arial.ttf", 30)
            genre_font = ImageFont.truetype("arial.ttf", 30)
        except:
            title_font = ImageFont.load_default()
            meta_font = ImageFont.load_default()
            plot_font = ImageFont.load_default()
            genre_font = ImageFont.load_default()

        # Title
        # textwrap for title? Usually title is short enough or we start new line
        current_y = 100
        
        # Draw Title
        draw.text((text_start_x, current_y), str(title), font=title_font, fill="white")
        current_y += 80
        
        # Meta: Year | Rating
        meta_text = f"{year}   |   ⭐ {rating}"
        draw.text((text_start_x, current_y), meta_text, font=meta_font, fill="#FFD700") # Gold color
        current_y += 60
        
        # Genres
        if genres:
             # Draw simplified genre tags logic or just text
             draw.text((text_start_x, current_y), str(genres), font=genre_font, fill="#A0A0A0")
             current_y += 60

        # Divider
        draw.line([(text_start_x, current_y), (text_start_x + 300, current_y)], fill="white", width=2)
        current_y += 40

        # Plot
        import textwrap
        plot_lines = textwrap.wrap(str(plot), width=50) # Approx char width
        for line in plot_lines[:6]: # Limit lines
            draw.text((text_start_x, current_y), line, font=plot_font, fill="white")
            current_y += 40

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
                
                # Place from right to left at bottom
                current_x = width - 60
                bottom_y = height - 60 - logo_size
                
                for p in reversed(resized_providers):
                    current_x -= p.width
                    canvas.paste(p, (current_x, bottom_y), p if p.mode == 'RGBA' else None)
                    current_x -= padding
                    
        # Output
        out_io = BytesIO()
        canvas = canvas.convert("RGB")
        canvas.save(out_io, 'JPEG', quality=95)
        out_io.seek(0)
        return out_io
