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
from typing import Set, List, Tuple, Optional

# Fix Windows console encoding issues with special characters
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8') # type: ignore
    except AttributeError:
        pass

DOWNLOAD_DIR = "CAD_Files"
DRY_RUN = False

STANDARD_CATEGORIES = {
    "electronics": "ELECTRONICS",
    "hardware": "HARDWARE",
    "kits": "KITS",
    "motion": "MOTION",
    "structure": "STRUCTURE",
    "ftc": "STRUCTURE", 
    "mechanical": "MOTION",
}

def clean_filename(name: str) -> str:
    name = re.sub(r'\d{4} Series\s*', '', name)
    name = re.sub(r'goBILDA®?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'REV Robotics', '', name, flags=re.IGNORECASE)
    name = re.sub(r'AndyMark', '', name, flags=re.IGNORECASE)
    name = name.replace('™', '').replace('®', '').replace('©', '')
    name = name.replace('(', '').replace(')', '').replace(',', '')
    name = name.replace(':', ' ')
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    return name.strip()

def normalize_category(cat: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', " ", cat).strip()
    cleaned = re.sub(r'\s+', " ", cleaned)
    lower_cat = cleaned.lower()
    for key, val in STANDARD_CATEGORIES.items():
        if key in lower_cat:
            return val
    return cleaned.upper() if cleaned else "UNCATEGORIZED"

def download_cad_file(file_url: str, target_folder: str, clean_name: str) -> None:
    try:
        response = requests.get(file_url, stream=True, timeout=15)
        response.raise_for_status()
        
        dest_path = os.path.join(target_folder, f"{clean_name}.step")
        
        # Check if it's a zip by url or content type
        is_zip = file_url.lower().endswith('.zip') or 'zip' in response.headers.get('Content-Type', '').lower()
        
        if is_zip:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip', mode='wb') as tmp:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                tmp_path = tmp.name
                
            with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                step_files = [f for f in zip_ref.namelist() if f.lower().endswith('.step') or f.lower().endswith('.stp')]
                if step_files:
                    step_file_in_zip = step_files[0]
                    source = zip_ref.open(step_file_in_zip)
                    with open(dest_path, "wb") as target:
                        target.write(source.read())
                    source.close()
                    print(f"     Successfully extracted and saved: {dest_path}")
                else:
                     print(f"     No .step file found in downloaded zip for {clean_name}")
            os.remove(tmp_path)
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.step', mode='wb') as tmp:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                tmp_path = tmp.name
            import shutil
            shutil.move(tmp_path, dest_path)
            print(f"     Successfully saved: {dest_path}")
            
    except Exception as e:
        print(f"     Failed to download CAD {clean_name}: {e}")


class BaseScraper:
    name = "Base"
    base_url = ""
    
    def run(self):
        print(f"\n--- Starting {self.name} Scraper ---")
        urls = self.get_all_product_urls()
        
        urls_to_process = urls[:50] if DRY_RUN else urls
        print(f"\nFound {len(urls)} total products for {self.name}.")
        
        for i, prod_url in enumerate(urls_to_process):
            print(f"\n[{self.name}] Processing {i+1}/{len(urls_to_process)}... ({prod_url})")
            try:
                self.process_product(prod_url)
            except Exception as e:
                print(f"Error processing {prod_url}: {e}")
            time.sleep(0.5)

    def get_all_product_urls(self) -> List[str]:
        return []
        
    def process_product(self, product_url: str):
        pass

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None


class GobildaScraper(BaseScraper):
    name = "goBILDA"
    base_url = "https://www.gobilda.com"
    
    def get_all_product_urls(self) -> List[str]:
        print("Fetching sitemap index from goBILDA...")
        index_url = "https://www.gobilda.com/xmlsitemap.php"
        all_urls: Set[str] = set()
        
        try:
            r = requests.get(index_url, timeout=10)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            sitemaps = root.findall('ns:sitemap/ns:loc', namespaces)
            if not sitemaps:
                sitemaps = [e for e in root.iter() if 'loc' in e.tag]
                
            target_sitemaps = [e.text for e in sitemaps if e.text is not None and ('type=products' in e.text or 'type=categories' in e.text)]
            
            for sm in target_sitemaps:
                if not sm: continue
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
        except Exception as e:
            print(f"Error fetching sitemap: {e}")
            
        return self._discover_all_pages(list(all_urls))
        
    def _spider_url(self, url: str, visited: Set[str]) -> Tuple[Set[str], Set[str]]:
        new_links: Set[str] = set()
        found_products: Set[str] = set()
        
        if url.count('/') >= 3:
             found_products.add(url)
             
        try:
            html = requests.get(url, timeout=10).text
            all_raw_links = set(re.findall(r'https://www\.gobilda\.com/[a-zA-Z0-9\-\/]+', html))
            
            for full_url in all_raw_links:
                if full_url not in visited:
                    skip_words = ['/login', '/cart', '/checkout', '/account', '/search', '/wishlist', '/policies', '/support', '/contact', '/blog', '/about', '.png', '.jpg', '.pdf', '/content/']
                    if not any(word in full_url.lower() for word in skip_words):
                        new_links.add(full_url)
        except Exception:
            pass
            
        return new_links, found_products
        
    def _discover_all_pages(self, start_urls: List[str]) -> List[str]:
        print(f"\nCrawling to find hidden variants (Starting with {len(start_urls)} URLs)...")
        visited: Set[str] = set()
        to_visit: Set[str] = set(start_urls)
        all_products: Set[str] = set()
        max_hops = 3
        
        for hop in range(max_hops):
            if not to_visit: break
            print(f"  Hop {hop+1}: Scanning {len(to_visit)} pages (This might take a minute)...")
            next_to_visit: Set[str] = set()
            
            current_batch = [url for url in to_visit if url not in visited]
            visited.update(current_batch)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(self._spider_url, url, visited) for url in current_batch]
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        new_links, found_prods = future.result() # type: ignore
                        next_to_visit.update(new_links)
                        all_products.update(found_prods)
                    except Exception:
                        pass
            
            to_visit = next_to_visit
            
        all_products.update(start_urls) 
        final_products = []
        skip_words = ['/login', '/cart', '/checkout', '/account', '/search', '/wishlist', '/policies', '/support', '/contact', '/blog', '/about', '.png', '.jpg', '.pdf', '/content/']
        for p in all_products:
            if p.count('/') >= 3 and not any(word in p.lower() for word in skip_words):
                final_products.append(p)
        return list(set(final_products))
        
    def process_product(self, product_url: str):
        soup = self._get_soup(product_url)
        if not soup: return

        title_el = soup.select_one('h1.productView-title')
        if not title_el: return
        raw_name = title_el.text.strip()
        clean_name = clean_filename(raw_name)

        breadcrumbs = []
        bc_elements = soup.select('.breadcrumbs .breadcrumb a')
        for bc in bc_elements:
            text = bc.text.strip()
            if text.lower() not in ["home", "products"]: 
                breadcrumbs.append(normalize_category(text))
                
        if not breadcrumbs:
            breadcrumbs = ["UNCATEGORIZED"]

        step_link = None
        links = soup.select('a')
        for link in links:
            text = link.text.strip().lower()
            if "step file" in text:
                href = link.get('href')
                if href:
                    step_link = urljoin(self.base_url, href)
                    break
                    
        if not step_link: return

        folder_path = os.path.join(DOWNLOAD_DIR, *breadcrumbs)
        if len(str(folder_path)) > 150:
             folder_path = str(folder_path)[:150]

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
            download_cad_file(step_link, folder_path, clean_name)


class RevScraper(BaseScraper):
    name = "REV Robotics"
    base_url = "https://www.revrobotics.com"
    
    def get_all_product_urls(self) -> List[str]:
        print("Fetching sitemap from REV Robotics...")
        index_url = "https://www.revrobotics.com/xmlsitemap.php"
        all_urls: Set[str] = set()
        
        try:
            r = requests.get(index_url, timeout=10)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
                
                sitemaps = root.findall('ns:sitemap/ns:loc', namespaces)
                if not sitemaps:
                    sitemaps = [e for e in root.iter() if 'loc' in e.tag]
                    
                target_sitemaps = [e.text for e in sitemaps if e.text is not None and 'type=products' in e.text]
                
                for sm in target_sitemaps:
                    if not sm: continue
                    print(f"  -> Reading {sm}")
                    sr = requests.get(sm, timeout=15)
                    sroot = ET.fromstring(sr.content)
                    
                    locs = sroot.findall('ns:url/ns:loc', namespaces)
                    if not locs:
                        locs = [e for e in sroot.iter() if 'loc' in e.tag]
                        
                    for loc in locs:
                        if loc.text:
                            all_urls.add(loc.text)
        except Exception as e:
            print(f"Error fetching REV sitemap: {e}")
            
        return list(all_urls)
        
    def process_product(self, product_url: str):
        soup = self._get_soup(product_url)
        if not soup: return

        title_el = soup.select_one('h1.productView-title')
        if not title_el: return
        raw_name = title_el.text.strip()
        clean_name = clean_filename(raw_name)

        breadcrumbs = []
        bc_elements = soup.select('.breadcrumbs .breadcrumb a')
        for bc in bc_elements:
            text = bc.text.strip()
            if text.lower() not in ["home", "products", "ftc", "frc"]: 
                breadcrumbs.append(normalize_category(text))
                
        if not breadcrumbs:
            breadcrumbs = ["UNCATEGORIZED"]

        step_link = None
        # REV usually has STEP files labeled "STEP File" or ends with .step
        links = soup.select('a')
        for link in links:
            text = link.text.strip().lower()
            href = link.get('href', '')
            if "step" in text or href.lower().endswith('.step') or href.lower().endswith('.stp'):
                if href and not href.startswith('javascript'):
                    step_link = urljoin(self.base_url, href)
                    break
                    
        if not step_link: return

        folder_path = os.path.join(DOWNLOAD_DIR, *breadcrumbs)
        if len(str(folder_path)) > 150:
             folder_path = str(folder_path)[:150]

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
            download_cad_file(step_link, folder_path, clean_name)


class AndyMarkScraper(BaseScraper):
    name = "AndyMark"
    base_url = "https://www.andymark.com"
    
    def get_all_product_urls(self) -> List[str]:
        print("Fetching sitemap from AndyMark...")
        index_url = "https://www.andymark.com/sitemap.xml" # They use Shopify style sitemap now
        all_urls: Set[str] = set()
        
        try:
            r = requests.get(index_url, timeout=10)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
                
                sitemaps = root.findall('ns:sitemap/ns:loc', namespaces)
                if not sitemaps:
                    sitemaps = [e for e in root.iter() if 'loc' in e.tag]
                    
                target_sitemaps = [e.text for e in sitemaps if e.text is not None and 'products' in e.text]
                
                for sm in target_sitemaps:
                    if not sm: continue
                    print(f"  -> Reading {sm}")
                    sr = requests.get(sm, timeout=15)
                    sroot = ET.fromstring(sr.content)
                    
                    locs = sroot.findall('ns:url/ns:loc', namespaces)
                    if not locs:
                        locs = [e for e in sroot.iter() if 'loc' in e.tag]
                        
                    for loc in locs:
                        if loc.text:
                            all_urls.add(loc.text)
        except Exception as e:
            print(f"Error fetching AndyMark sitemap: {e}")
            
        return list(all_urls)
        
    def process_product(self, product_url: str):
        soup = self._get_soup(product_url)
        if not soup: return

        # AndyMark uses different classes sometimes
        title_el = soup.select_one('h1.product-title') 
        if not title_el:
            title_el = soup.select_one('h1')
            if not title_el: return
            
        raw_name = title_el.text.strip()
        clean_name = clean_filename(raw_name)

        breadcrumbs = []
        bc_elements = soup.select('.breadcrumb li a')
        for bc in bc_elements:
            text = bc.text.strip()
            if text.lower() not in ["home", "products", "all", "shop"]: 
                breadcrumbs.append(normalize_category(text))
                
        if not breadcrumbs:
            breadcrumbs = ["UNCATEGORIZED"]

        step_link = None
        links = soup.select('a')
        for link in links:
            text = link.text.strip().lower()
            href = link.get('href', '')
            if "step" in text or href.lower().endswith('.step') or href.lower().endswith('.stp'):
                if href and not href.startswith('javascript'):
                    step_link = urljoin(self.base_url, href)
                    break
                    
        if not step_link: return

        folder_path = os.path.join(DOWNLOAD_DIR, *breadcrumbs)
        if len(str(folder_path)) > 150:
             folder_path = str(folder_path)[:150]

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
            download_cad_file(step_link, folder_path, clean_name)

def main():
    print("====================================")
    print("        CadGrab FTC Scraper         ")
    print("====================================")
    if DRY_RUN:
        print("!!! RUNNING IN DRY_RUN MODE. Files will NOT be downloaded. !!!")
    
    print("\nSelect websites to scrape CAD parts from:")
    print("[1] goBILDA")
    print("[2] REV Robotics")
    print("[3] AndyMark")
    print("[4] ALL of the above")
    
    try:
        choice = input("\nEnter choice (1-4): ").strip()
    except EOFError:
        choice = "1"
        
    scrapers_to_run = []
    
    if choice == '1':
        scrapers_to_run.append(GobildaScraper())
    elif choice == '2':
        scrapers_to_run.append(RevScraper())
    elif choice == '3':
        scrapers_to_run.append(AndyMarkScraper())
    elif choice == '4':
        scrapers_to_run.append(GobildaScraper())
        scrapers_to_run.append(RevScraper())
        scrapers_to_run.append(AndyMarkScraper())
    else:
        print("Invalid choice. Defaulting to goBILDA.")
        scrapers_to_run.append(GobildaScraper())
        
    for scraper in scrapers_to_run:
        scraper.run()
        
    print("\nAll tasks completed!")

if __name__ == "__main__":
    main()
