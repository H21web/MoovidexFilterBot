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
            title_font = ImageFont.truetype("arial.ttf", 60)
            meta_font = ImageFont.truetype("arial.ttf", 35)
            plot_font = ImageFont.truetype("arial.ttf", 30)
            genre_font = ImageFont.truetype("arial.ttf", 30)
        except IOError:
            try:
                # Try common Linux font
                title_font = ImageFont.truetype("DejaVuSans.ttf", 60)
                meta_font = ImageFont.truetype("DejaVuSans.ttf", 35)
                plot_font = ImageFont.truetype("DejaVuSans.ttf", 30)
                genre_font = ImageFont.truetype("DejaVuSans.ttf", 30)
            except IOError:
                title_font = ImageFont.load_default()
                meta_font = ImageFont.load_default()
                plot_font = ImageFont.load_default()
                genre_font = ImageFont.load_default()
                using_default = True

        # Clean text if using default font or just generally to be safe from smart quotes
        # We always apply basic replacement, and aggressive strip if default font
        if using_default:
            title = clean_text_safe(title)
            year = clean_text_safe(year)
            rating = clean_text_safe(rating)
            genres = clean_text_safe(genres)
            plot = clean_text_safe(plot)
        else:
            # Just do simple replacements for smart quotes even with good fonts to be tidy
            replacements = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "…": "..."}
            for k, v in replacements.items():
                plot = str(plot).replace(k, v)
                title = str(title).replace(k, v)

        # Draw Title
        current_y = 100
        draw.text((text_start_x, current_y), str(title), font=title_font, fill="white")
        current_y += 80
        
        meta_text = f"{year}   |   Rat: {rating}"
        draw.text((text_start_x, current_y), meta_text, font=meta_font, fill="#FFD700")
        current_y += 60
        
        if genres:
             draw.text((text_start_x, current_y), str(genres), font=genre_font, fill="#A0A0A0")
             current_y += 60

        # Divider
        draw.line([(text_start_x, current_y), (text_start_x + 300, current_y)], fill="white", width=2)
        current_y += 40

        import textwrap
        plot = str(plot) if plot else "No description available."
        plot_lines = textwrap.wrap(plot, width=50)
        for line in plot_lines[:6]:
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
                
                current_x = width - 60
                bottom_y = height - 60 - logo_size
                
                for p in reversed(resized_providers):
                    current_x -= p.width
                    canvas.paste(p, (current_x, bottom_y), p if p.mode == 'RGBA' else None)
                    current_x -= padding
                    
        out_io = BytesIO()
        canvas = canvas.convert("RGB")
        canvas.save(out_io, 'JPEG', quality=95)
        out_io.seek(0)
        return out_io
