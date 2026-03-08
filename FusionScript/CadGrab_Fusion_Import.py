import adsk.core, adsk.fusion, adsk.cam, traceback
import os

def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface

        # 1. Ask user for the root directory containing the STEP files
        folderDialog = ui.createFolderDialog()
        folderDialog.title = 'Select the CAD_Files folder downloaded by CadGrab'
        dialogResult = folderDialog.showDialog()
        
        if dialogResult == adsk.core.DialogResults.DialogOK:
            inputFolder = folderDialog.folder
        else:
            return

        # 2. Setup the Import Manager and Target Project Folder
        importManager = app.importManager
        targetProjectFolder = app.data.activeProject.rootFolder

        # 3. Setup Progress Dialog
        progressDialog = ui.createProgressDialog()
        progressDialog.cancelButtonText = 'Cancel'
        progressDialog.isBackgroundDependent = False
        progressDialog.isCancelButtonShown = True
        
        # Count total files to setup the progress bar size
        total_files = 0
        for root, dirs, files in os.walk(inputFolder):
            for file in files:
                if file.lower().endswith('.step'):
                    total_files += 1
                    
        progressDialog.show('Bulk Importing CadGrab Models...', 'Starting Import...', 0, total_files, 1)
        files_imported = 0
        files_skipped = 0

        # Recursive function to walk local files and create matching cloud folders
        def process_directory(local_path, current_cloud_folder):
            nonlocal files_imported, files_skipped
            
            for item in os.listdir(local_path):
                # Allow user to abort
                if progressDialog.wasCancelled:
                    return
                
                full_path = os.path.join(local_path, item)
                
                # If it's a directory, recreate it in Fusion 360
                if os.path.isdir(full_path):
                    next_cloud_folder = None
                    # Check if the folder already exists in the cloud to prevent duplicates
                    for df in current_cloud_folder.dataFolders:
                        if df.name == item:
                            next_cloud_folder = df
                            break
                    
                    if not next_cloud_folder:
                        next_cloud_folder = current_cloud_folder.dataFolders.add(item)
                    
                    # Recurse deeper
                    process_directory(full_path, next_cloud_folder)
                
                # If it's a STEP file, upload it
                elif item.lower().endswith('.step'):
                    base_name = os.path.splitext(item)[0]
                    
                    # Check if file with exact name already exists in this specific cloud folder
                    exists = False
                    for df in current_cloud_folder.dataFiles:
                        if df.name == base_name:
                            exists = True
                            break
                    
                    if not exists:
                        progressDialog.message = f'Uploading: {item}'
                        # Import the item to the Data Panel (upload)
                        stepOptions = importManager.createSTEPImportOptions(full_path)
                        importManager.importToDataFile(stepOptions, current_cloud_folder)
                        files_imported += 1
                    else:
                        files_skipped += 1
                    
                    progressDialog.progressValue = files_imported + files_skipped
                    adsk.doEvents()

        ui.messageBox(f"Ready to import {total_files} models into the active project '{app.data.activeProject.name}'.\n\nThis will take a while. You can cancel at any time via the progress bar.")
        
        # Begin Import
        process_directory(inputFolder, targetProjectFolder)
        
        progressDialog.hide()
        
        if progressDialog.wasCancelled:
            ui.messageBox(f'Import cancelled by user.\nSuccessfully uploaded {files_imported} files before stopping.\nSkipped {files_skipped} pre-existing files.')
        else:
            ui.messageBox(f'Import Complete!\n\nSuccessfully uploaded {files_imported} models.\nSkipped {files_skipped} models that already existed.')

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
