import requests
from bs4 import BeautifulSoup
import os
import re
import zipfile
import tempfile
import time
import sys
import xml.etree.ElementTree as ET
import concurrent.futures
from urllib.parse import urljoin

# Fix Windows console encoding issues with special characters like trademarks
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Setup Base URL and directories
BASE_URL = "https://www.gobilda.com"
DOWNLOAD_DIR = "CAD_Files"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Whether to just log what would be downloaded without actually downloading
DRY_RUN = False

def get_soup(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def get_all_product_urls_from_sitemap():
    import xml.etree.ElementTree as ET
    print("Fetching sitemap index from goBILDA...")
def get_all_product_urls_from_sitemap():
    import xml.etree.ElementTree as ET
    print("Fetching sitemap index from goBILDA...")
    index_url = "https://www.gobilda.com/xmlsitemap.php"
    
    try:
        r = requests.get(index_url, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        
        # BigCommerce uses standard sitemap XML namespaces
        namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # Find product AND category sitemaps to ensure we miss nothing
        sitemaps = root.findall('ns:sitemap/ns:loc', namespaces)
        if not sitemaps:
            sitemaps = [e for e in root.iter() if 'loc' in e.tag]
            
        target_sitemaps = [e.text for e in sitemaps if e.text and ('type=products' in e.text or 'type=categories' in e.text)]
        
        all_urls = set()
        for sm in target_sitemaps:
            print(f"  -> Reading {sm}")
            sr = requests.get(sm, timeout=15)
            sr.raise_for_status()
            sroot = ET.fromstring(sr.content)
            
            locs = sroot.findall('ns:url/ns:loc', namespaces)
            if not locs:
                locs = [e for e in sroot.iter() if 'loc' in e.tag]
                
            for loc in locs:
                if loc.text:
                    all_urls.add(loc.text)
                    
        return all_urls
        
    except Exception as e:
        print(f"Error fetching sitemap: {e}")
        return set()

def spider_url(url, visited):
    """Worker function to fetch a single URL and regex all links."""
    new_links = set()
    found_products = set()
    
    # If it looks like a goBILDA path, save it. Wait to verify it has a step file during processing.
    if url.count('/') >= 3:
         found_products.add(url)
         
    try:
        html = requests.get(url, timeout=10).text
        all_raw_links = set(re.findall(r'https://www\.gobilda\.com/[a-zA-Z0-9\-\/]+', html))
        
        for full_url in all_raw_links:
            if full_url not in visited:
                # Exclude clearly non-product pages
                skip_words = ['/login', '/cart', '/checkout', '/account', '/search', '/wishlist', '/policies', '/support', '/contact', '/blog', '/about', '.png', '.jpg', '.pdf', '/content/']
                if not any(word in full_url.lower() for word in skip_words):
                    new_links.add(full_url)
    except Exception as e:
        # Suppress errors to keep output clean, some pages are just dead
        pass
        
    return new_links, found_products

def discover_all_pages(start_urls):
    """
    Crawls from a set of starting URLs to find all reachable product pages.
    Uses multi-threading to speed up the scanning of thousands of pages.
    """
    print(f"\nCrawling to find hidden variants (Starting with {len(start_urls)} URLs)...")
    visited = set()
    to_visit = set(start_urls)
    all_products = set()
    
    # We don't want to crawl forever. We'll limit depth/iterations.
    max_hops = 3
    
    for hop in range(max_hops):
        if not to_visit:
            break
            
        print(f"  Hop {hop+1}: Scanning {len(to_visit)} pages (This might take a minute)...")
        next_to_visit = set()
        
        # Lock visited set from the main thread before dispatching
        current_batch = [url for url in to_visit if url not in visited]
        visited.update(current_batch)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            # Submit all URL fetching tasks
            future_to_url = {executor.submit(spider_url, url, visited): url for url in current_batch}
            
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    new_links, found_prods = future.result()
                    next_to_visit.update(new_links)
                    all_products.update(found_prods)
                except Exception as exc:
                    pass
        
        to_visit = next_to_visit
        
    # Combine everything we found
    all_products.update(start_urls) 
    # Clean up standard non-product pages
    final_products = []
    skip_words = ['/login', '/cart', '/checkout', '/account', '/search', '/wishlist', '/policies', '/support', '/contact', '/blog', '/about', '.png', '.jpg', '.pdf', '/content/']
    for p in all_products:
        if p.count('/') >= 3 and not any(word in p.lower() for word in skip_words):
            final_products.append(p)
    return list(set(final_products))

def clean_filename(name):
    # Shorten names by removing redundant "Series" designators
    name = re.sub(r'\d{4} Series\s*', '', name)
    
    # Remove things like "goBILDA®"
    name = re.sub(r'goBILDA®?', '', name, flags=re.IGNORECASE)
    
    # Remove trademarks
    name = name.replace('™', '').replace('®', '')
    
    # Clean up parenthesis formatting: "U-Channel (3 Hole, 96mm Length)" -> "U-Channel 3 Hole 96mm Length"
    name = name.replace('(', '').replace(')', '').replace(',', '')
    
    # Replace colons with space to preserve meaning (e.g. 1:1 Ratio -> 1 1 Ratio)
    name = name.replace(':', ' ')
    
    # Replace illegal characters for Windows/Fusion
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    
    return name.strip()

def process_product(product_url):
    soup = get_soup(product_url)
    if not soup:
        return

    # Extract Product Name from H1
    title_el = soup.select_one('h1.productView-title')
    if not title_el:
        return
    raw_name = title_el.text.strip()
    clean_name = clean_filename(raw_name)

    # Extract Breadcrumbs for Folder Structure
    breadcrumbs = []
    bc_elements = soup.select('.breadcrumbs .breadcrumb a')
    for bc in bc_elements:
        text = bc.text.strip()
        if text.lower() not in ["home", "products"]: # Skip root levels
            # Replace illegal Windows path characters with a space
            text = re.sub(r'[\\/*?:"<>|]', " ", text).strip()
            # Collapse any double spaces created by the regex
            text = re.sub(r'\s+', " ", text)
            breadcrumbs.append(text)
            
    if not breadcrumbs:
        breadcrumbs = ["Uncategorized"]

    # Locate STEP File Download link
    step_link = None
    links = soup.select('a')
    for link in links:
        text = link.text.strip().lower()
        if "step file" in text:
            href = link.get('href')
            if href:
                step_link = urljoin(BASE_URL, href)
                break
                
    if not step_link:
        # Some products might not have a STEP file
        return

    # Create directory structure
    folder_path = os.path.join(DOWNLOAD_DIR, *breadcrumbs)
    
    # Avoid path length limit issues (Windows MAX_PATH is 260)
    # Simple heuristic to truncate folder names if getting long
    if len(folder_path) > 150:
         folder_path = folder_path[:150]

    if not DRY_RUN:
        os.makedirs(folder_path, exist_ok=True)
    
    print(f"[{'DRY-RUN' if DRY_RUN else 'DOWNLOADING'}] {clean_name}")
    print(f"  -> Path: {folder_path}")
    print(f"  -> Link: {step_link}")

    if not DRY_RUN:
        expected_dest_path = os.path.join(folder_path, f"{clean_name}.step")
        if os.path.exists(expected_dest_path):
            print(f"[SKIPPED] {clean_name} already exists.")
            return

        download_and_extract_step(step_link, folder_path, clean_name)

def download_and_extract_step(zip_url, target_folder, clean_name):
    # Download the zip file
    try:
        response = requests.get(zip_url, stream=True, timeout=15)
        response.raise_for_status()
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
            for chunk in response.iter_content(chunk_size=8192):
                tmp.write(chunk)
            tmp_path = tmp.name
            
        # Extract the STEP file
        with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
            # Find the step file inside
            step_files = [f for f in zip_ref.namelist() if f.lower().endswith('.step')]
            if step_files:
                step_file_in_zip = step_files[0] # Usually just one
                
                # Construct final dest path
                dest_path = os.path.join(target_folder, f"{clean_name}.step")
                
                # Extract and rename
                source = zip_ref.open(step_file_in_zip)
                with open(dest_path, "wb") as target:
                    target.write(source.read())
                source.close()
                print(f"     Successfully saved: {dest_path}")
            else:
                 print(f"     No .step file found in downloaded zip for {clean_name}")
                 
        os.remove(tmp_path)
    except Exception as e:
        print(f"     Failed to download/extract {clean_name}: {e}")

def main():
    print("Starting CadGrab Scraper...")
    if DRY_RUN:
        print("!!! RUNNING IN DRY_RUN MODE. Files will NOT be downloaded. Set DRY_RUN=False to download. !!!")
    
    base_urls = get_all_product_urls_from_sitemap()
    all_product_urls = discover_all_pages(base_urls)
    
    print(f"\nFound {len(all_product_urls)} total products after deep crawl.")
    
    for i, prod_url in enumerate(all_product_urls[:50 if DRY_RUN else None]):
        print(f"\nProcessing {i+1}/{len(all_product_urls)}... ({prod_url})")
        process_product(prod_url)
        time.sleep(0.5) # Gentle rate limiting

if __name__ == "__main__":
    main()
