# GoBilda Parts (CadGrab Scraped)

Here are the complete STEP files from goBILDA, scraped and organized by the [CadGrab scraper](https://github.com/Marcus-Minions/CadGrab). You can download a compressed zip file of all the CAD files [here](https://drive.google.com/file/d/1TfamsgN20bg8ngEluyXsut2uvdDQl5Pa/view?usp=sharing).

Collected by **Krshs90**, a contributor to the **[Marcus Minions](https://github.com/Marcus-Minions)** #22077.

### Bulk Importing to Fusion 360
If you want to manually upload these parts to Fusion 360 while keeping the perfect folder structure, this repository includes a custom [Fusion 360 Bulk Importer Extension](https://github.com/Marcus-Minions/CadGrab/tree/master/FusionScript).

---

# CadGrab

CadGrab is a powerful, automated Python scraper and download manager designed to extract, organize, and rename CAD (`.step`) files from the entire goBILDA robotics catalog.

Developed by **Krshs90**, a contributor to the **[Marcus Minions](https://github.com/Marcus-Minions)** #22077.

Bug fixed by **Google Antigravity**
ReadMe created by **Gemini 3.1 Pro**

## How it Works

Unlike standard web scrapers, goBILDA hides the vast majority of its product variations (like lengths of U-Channel or ratios of motors) inside Javascript rendering engines, making them invisible to standard crawling.

**CadGrab solves this with a two-part engine:**
1. **Sitemap Extraction:** It parses goBILDA's raw XML sitemaps to discover every base product category.
2. **Universal Multithreaded Regex Spider:** It spawns 20 parallel threads to download the raw code of thousands of webpages simultaneously. It then uses targeted Regular Expressions (Regex) to rip every single valid product URL out of the page's hidden code, bypassing Javascript obfuscation completely.

## Features


- **Smart Directory Organization:** Reads website breadcrumbs to automatically create a perfect categorized folder directory (e.g., `CAD_Files/MOTION/Motors/Yellow Jacket Planetary Gear Motors`).
- **Path Sanitization:** Automatically truncates folder paths and removes invalid characters (e.g. `3/16"`) to prevent Windows crashes and abide by `MAX_PATH` length constraints.
- **Auto-Renaming:** Standardizes and shortens file names (removes trademark symbols and long "Series" prefixes) to keep them clean for CAD software like Fusion.
- **Duplicate Skipping:** If you stop the script halfway, running it again will instantly skip all the files you already successfully downloaded, saving bandwidth and time.

## Setup & Requirements

1. Ensure **Python 3.8+** is installed on your system.
2. Clone this repository to your computer.
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Open `cad_grab.py` in any text editor.
2. By default, `DRY_RUN = False`. If you set it to `True`, the script will only scan the site and print what it *would* download, without actually saving the files.
3. Run the script:
   ```bash
   python cad_grab.py
   ```
4. Sit back and relax. The script will create a root `CAD_Files` directory and begin placing thousands of `.step` files perfectly into their respective categorized sub-folders.

## Output

Files will be saved in a newly created directory named `CAD_Files` within the script's folder. 

## Fusion 360 Bulk Importer
If you want to quickly bulk import the downloaded `.step` files and perfectly match their exact folder structure inside your Autodesk Fusion 360 Data Panel cloud, this repository includes a custom Fusion 360 Add-In script!

1. Open Fusion 360 and go to **Design** workspace.
2. Select **Utilities** > **Scripts and Add-Ins** (Shift + S).
3. Under the **Scripts** tab, click the green `+` icon next to **My Scripts**.
4. Select the `FusionScript` folder located inside your cloned `CadGrab` directory.
5. `CadGrab_Fusion_Import` should appear in the list! Select it and click **Run**.
6. A dialog will prompt you to open the exact `CAD_Files` folder that the CadGrab scraper downloaded.
7. Sit back! A progress bar will appear while Fusion automatically creates all your categories in your cloud Project and imports thousands of files for you. **Note: This process can take a significant amount of time depending on the number of files and your internet upload speed. For example, importing the entire goBILDA library takes approximately 3 hours.** (If you cancel it, running it again will automatically skip duplicates!)

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
