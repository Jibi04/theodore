from pathlib import Path
import json
from theodore.core.utils import DATA_DIR

# --------------------
# UTTERANCES
# --------------------

DEFAULT_TRAIN_DATA = {
    "SHOW-DASH": [
        "Open the monitoring board", "Show me the dashboard", "How is the system performing?", 
        "View resource stats", "Bring up the system health overview", "Launch the performance monitor", 
        "Show me the live analytics", "How are the system metrics looking?", "Open the status panel", 
        "Display the resource usage dashboard"
    ],

    "CUSTOM-SHELL": [
        "Run a custom bash script", "Open the terminal", "Execute a shell command", 
        "I need to run some git commands", "Run this bash string", "Invoke a custom terminal instruction", 
        "Trigger a manual shell script", "Execute command in the background", "I have a bash snippet to run", 
        "Open a subprocess for this command"
    ],

    "ALEMBIC-UPGRADE": [
        "Apply the latest database migrations", "Bring the database schema up to date", 
        "Upgrade the database to the newest version", "Run all pending migrations", 
        "Move the database forward to the latest revision", "Update the schema using migrations", 
        "Perform a database migration upgrade", "Sync the schema with the latest models", 
        "Push pending alembic changes", "Update the DB structure"
    ],

    "ALEMBIC-DOWNGRADE": [
        "Roll back the last database migration", "Revert the database schema", 
        "Downgrade the database to a previous version", "Undo the most recent migration", 
        "Step back one database revision", "Restore the schema to an earlier state", 
        "Downgrade the alembic revision", "Revert the last DB schema change", 
        "Go back to the previous migration state", "Reverse the recent database update"
    ],

    "ALEMBIC-MIGRATE": [
        "Update the database records", "Apply changes to the database", "Sync the database with new data", 
        "Modify existing entries in the database", "Run database updates", "Push data changes to the database", 
        "Execute a data migration", "Apply record-level updates to the DB", "Process the data migration script", 
        "Commit structural data changes"
    ],

    "GIT-COMMIT": [
        "Save my changes to version control", "Commit the current work", "Create a new commit", 
        "Record these changes", "Checkpoint my progress", "Finalize the current changes", 
        "Snapshop the current code state", "Commit these updates with a message", 
        "Register my latest changes in git", "Store these modifications in the repository"
    ],

    "GIT-ADD": [
        "Stage the modified files", "Add files to the staging area", "Prepare these files for commit", 
        "Mark the changes to be committed", "Add updated files to git", "Stage everything I've changed", 
        "Move changes to the git index", "Track these new files", "Add all modifications for staging", 
        "Include these files in the next commit"
    ],

    "START-SERVERS": [
        "Run servers", "Start Processes", "Start the backend processes", 
        "Bring the servers online", "Initialize the system workers", "Spin up the background services", 
        "Boot up the backend server", "Kick off the main processes", "Get the servers running", 
        "Activate the service workers"
    ],

    "STOP-SERVERS": [
        "Shutdown the servers", "Stop running Processes", "Stop the backend processes", 
        "Take the servers offline", "Kill the background workers", "Terminate the server instances", 
        "Stop all active services", "Halt the system processes", "Shut down the backend", 
        "End the server tasks"
    ],

    "DIR-ORGANIZE": [
        "Clean up my desktop", "Sort my current folder", "Put these files where they belong", 
        "Automate my downloads movement", "Organize the directory structure", "File away these documents", 
        "Run the folder cleanup script", "Tidy up this directory", "Sort files into their categories", 
        "Arrange the files in this path"
    ],

    "WEATHER": [
        "Is it going to rain?", "What's the temperature?", "Should I take an umbrella?", 
        "Give me the forecast", "How is the weather outside?", "Tell me the conditions for today", 
        "What is the climate like in this area?", "Check the local weather report", 
        "Will it be sunny later?", "Give me a meteorological update"
    ],

    "DOWNLOAD": [
        "Download a file from this link", "Fetch this resource from the web", "Start a new file download", 
        "Grab this file for me", "Retrieve data from this URL", "Save this online file to disk", 
        "Initiate a download request", "Pull this file from the internet", "Download this item to my folder", 
        "Get this file via URL"
    ],

    "BACKUP": [
        "Upload my work to the cloud", "Start the rclone sync", "Secure my data", 
        "Run the cloud backup routine", "Sync my local files to the drive", "Perform a data backup", 
        "Mirror my directories to the cloud", "Protect my files with a backup", 
        "Push local data to remote storage", "Execute the rclone backup script"
    ],

    "SHOW-CONFIGS": [
        "Show me the system configuration", "List all settings", "Display the config file", 
        "What are the current parameters?", "View the application setup", "Check the config variables", 
        "Show my environment settings", "List the system configs", "Show the current setup", 
        "Open the configuration view"
    ],

    "PAUSE-DOWNLOAD": [
        "Pause the current download", "Stop the transfer temporarily", "Put the download on hold", 
        "Suspend the file fetching", "Pause this specific file download", "Halt the download progress", 
        "Temporarily stop the file download", "Freeze the current download", "Wait on this download", 
        "Pause active file transfers"
    ],

    "RESUME-DOWNLOAD": [
        "Resume the paused download", "Restart the file transfer", "Continue downloading this file", 
        "Pick up the download where it left off", "Unpause the download", "Keep fetching this file", 
        "Start the transfer again", "Resume the file download process", "Wake up the paused download", 
        "Proceed with the file acquisition"
    ]
}

TRAIN_DATA_DIR = DATA_DIR/"vector_embeddings"
TRAIN_DATA_DIR.mkdir(exist_ok=True, parents=True)

TRAIN_DATA_Path = TRAIN_DATA_DIR/"theodore_train_data.json"
if __name__ == "__main__":
    TRAIN_DATA_Path.write_text(json.dumps(DEFAULT_TRAIN_DATA))
    
    print("Done! \n", TRAIN_DATA_Path.as_posix())
