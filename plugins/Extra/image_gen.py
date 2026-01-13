import aiohttp
from PIL import Image, ImageFilter, ImageOps
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

async def generate_status_image(backdrop_url, poster_url, provider_urls):
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
        
        # 1. Backdrop
        if backdrop:
            # Resize backdrop to cover
            # Calculate aspect ratio
            bg_w, bg_h = backdrop.size
            ratio = max(width/bg_w, height/bg_h)
            new_size = (int(bg_w*ratio), int(bg_h*ratio))
            backdrop = backdrop.resize(new_size, Image.Resampling.LANCZOS)
            
            # Crop center
            left = (new_size[0] - width)/2
            top = (new_size[1] - height)/2
            backdrop = backdrop.crop((left, top, left+width, top+height))
            
            # Apply blur
            backdrop = backdrop.filter(ImageFilter.GaussianBlur(3))
            
            # Paste backdrop
            canvas.paste(backdrop, (0, 0))
            
            # Add darken overlay
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 100)) # 40% opacity black
            canvas = Image.alpha_composite(canvas, overlay)
        else:
             # Fallback background
             canvas = Image.new("RGBA", (width, height), (20, 20, 20))

        # 2. Poster
        if poster:
            # Resize poster
            # Target height: 600px (leaving 60px margin top/bottom)
            target_h = 600
            p_w, p_h = poster.size
            ratio = target_h / p_h
            new_p_w = int(p_w * ratio)
            poster = poster.resize((new_p_w, target_h), Image.Resampling.LANCZOS)
            
            # Add border
            # poster_with_border = ImageOps.expand(poster, border=5, fill='white')
            
            # Position: Left 60px, vertically centered
            pos_x = 60
            pos_y = (height - target_h) // 2
            
            canvas.paste(poster, (pos_x, pos_y), poster if poster.mode == 'RGBA' else None)
            
        # 3. Provider Logos
        if providers:
            providers = [p for p in providers if p]
            if providers:
                logo_size = 80
                padding = 20
                
                # We'll fix height to logo_size and adjust width maintaining aspect ratio
                resized_providers = []
                for p in providers:
                    pw, ph = p.size
                    ratio = logo_size / ph
                    new_pw = int(pw * ratio)
                    p_resized = p.resize((new_pw, logo_size), Image.Resampling.LANCZOS)
                    resized_providers.append(p_resized)
                
                start_x = width - 60 # Start from right margin
                # We need to place them from right to left
                
                current_x = width - 60
                bottom_y = height - 60 - logo_size
                
                # Place from right to left
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
