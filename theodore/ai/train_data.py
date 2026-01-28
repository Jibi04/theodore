# --------------------
# UTTERANCES
# --------------------

DEFAULT_TRAIN_DATA = dict(
    dash = [
        "Open the monitoring board", 
        "Show me the dashboard", 
        "How is the system performing?", 
        "View resource stats"
    ],

    shell = [
        "Run a custom bash script", 
        "Open the terminal", 
        "Execute a shell command", 
        "I need to run some git commands"
    ],
    alembic_upgrade = [
        "Apply the latest database migrations",
        "Bring the database schema up to date",
        "Upgrade the database to the newest version",
        "Run all pending migrations",
        "Move the database forward to the latest revision",
        "Update the schema using migrations"
    ],

    alembic_downgrade = [
        "Roll back the last database migration",
        "Revert the database schema",
        "Downgrade the database to a previous version",
        "Undo the most recent migration",
        "Step back one database revision",
        "Restore the schema to an earlier state"
    ],

    db_update = [
        "Update the database records",
        "Apply changes to the database",
        "Sync the database with new data",
        "Modify existing entries in the database",
        "Run database updates",
        "Push data changes to the database"
    ],

    git_commit = [
        "Save my changes to version control",
        "Commit the current work",
        "Create a new commit",
        "Record these changes",
        "Checkpoint my progress",
        "Finalize the current changes"
    ],

    git_add = [
        "Stage the modified files",
        "Add files to the staging area",
        "Prepare these files for commit",
        "Mark the changes to be committed",
        "Add updated files to git",
        "Stage everything I've changed"
    ],

    start_servers = [
        "Run servers",
        "Start Processes",
        "Start the backend processes",
        "Bring the servers online"
    ],

    stop_servers = [
        "Shutdown the servers",
        "Stop running Processes",
        "Stop the backend processes",
        "Take the servers offline"
    ],

    organize = [
        "Clean up my desktop", 
        "Sort my current folder", 
        "Put these files where they belong", 
        "Automate my downloads movement"
    ],

    weather = [
        "Is it going to rain?", 
        "What's the temperature?", 
        "Should I take an umbrella?", 
        "Give me the forecast"
    ],

    downloads = [
        "Track my active downloads", 
        "Get this file for me", 
        "Resume my download queue", 
        "Start the file downloader"
    ],

    backup = [
        "Upload my work to the cloud", 
        "Start the rclone sync", 
        "Secure my data", 
        "Run the backup script"
    ],

    configs = [
        "Change my settings", 
        "Open the preference file", 
        "Adjust the system configuration", 
        "Edit my defaults"
    ]
)
