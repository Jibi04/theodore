
train_data = [

    # =====================
    # FILE
    # =====================
    ("resume the download for report.pdf", {
        "entities": [(24, 34, "FILE")]
    }),
    ("move archive.tar.gz into the backup folder", {
        "entities": [(5, 21, "FILE")]
    }),
    ("upload config.json to cloud storage", {
        "entities": [(7, 18, "FILE")]
    }),
    ("delete the corrupted file data.db", {
        "entities": [(26, 33, "FILE")]
    }),
    ("compress logs.txt before uploading", {
        "entities": [(9, 17, "FILE")]
    }),

    # =====================
    # DIRECTORY
    # =====================
    ("store backups inside /var/backups", {
        "entities": [(12, 34, "DIRECTORY")]
    }),
    ("move files into the /tmp directory", {
        "entities": [(20, 24, "DIRECTORY")]
    }),
    ("scan everything under ~/projects", {
        "entities": [(22, 35, "DIRECTORY")]
    }),
    ("sync data from /home/user/data", {
        "entities": [(15, 30, "DIRECTORY")]
    }),
    ("clean the cache folder at /var/cache", {
        "entities": [(25, 35, "DIRECTORY")]
    }),

    # =====================
    # RCLONE_REMOTE
    # =====================
    ("sync backups to gdrive:", {
        "entities": [(16, 25, "RCLONE_REMOTE")]
    }),
    ("upload files into s3:", {
        "entities": [(18, 21, "RCLONE_REMOTE")]
    }),
    ("copy reports to dropbox:", {
        "entities": [(16, 25, "RCLONE_REMOTE")]
    }),
    ("push archives into onedrive:", {
        "entities": [(19, 31, "RCLONE_REMOTE")]
    }),
    ("mirror data to b2:", {
        "entities": [(15, 18, "RCLONE_REMOTE")]
    }),

    # =====================
    # CLOUD_PATH
    # =====================
    ("upload database dumps to gdrive:backups/2025", {
        "entities": [
            (25, 32, "RCLONE_REMOTE"),
            (32, 46, "CLOUD_PATH")
        ]
    }),
    ("store logs at s3:logs/app", {
        "entities": [
            (14, 17, "RCLONE_REMOTE"),
            (17, 25, "CLOUD_PATH")
        ]
    }),
    ("sync media to dropbox: media/photos", {
        "entities": [
            (14, 23, "RCLONE_REMOTE"),
            (23, 36, "CLOUD_PATH")
        ]
    }),

    # =====================
    # ENV_KEY
    # =====================
    ("use GDRIVE_NAME to authenticate uploads", {
        "entities": [(4, 15, "ENV_KEY")]
    }),
    ("load credentials from RCLONE_CONFIG", {
        "entities": [(22, 35, "ENV_KEY")]
    }),
    ("read cloud name from BACKUP_DRIVE", {
        "entities": [(21, 36, "ENV_KEY")]
    }),
    ("fallback to DEFAULT_REMOTE if missing", {
        "entities": [(12, 27, "ENV_KEY")]
    }),
    ("resolve path using DATA_DIR", {
        "entities": [(19, 27, "ENV_KEY")]
    }),

    # =====================
    # VALUE
    # =====================
    ("set task status to completed", {
        "entities": [(19, 28, "VALUE")]
    }),
    ("mark the job as pending", {
        "entities": [(16, 23, "VALUE")]
    }),
    ("compression level should be high", {
        "entities": [(28, 34, "VALUE")]
    }),

    # =====================
    # DATE_TIME
    # =====================
    ("schedule the backup for tomorrow", {
        "entities": [(24, 32, "DATE_TIME")]
    }),
    ("run cleanup next week", {
        "entities": [(12, 21, "DATE_TIME")]
    }),
    ("trigger sync at 9am monday", {
        "entities": [(16, 28, "DATE_TIME")]
    }),
]

# ----------------------------
# Load or create model
# ----------------------------
import spacy
from spacy.tokens import DocBin
from spacy.training import Example
import random

# 1. Start with a BLANK model to avoid fighting pre-trained weights
nlp = spacy.blank("en")
ner = nlp.add_pipe("ner")

# 2. Add ALL your custom labels
labels = set()
for _, ann in train_data:
    for _, _, label in ann["entities"]:
        labels.add(label)
for label in labels:
    ner.add_label(label)

# 3. Create a DocBin (The v3 way to handle data)
db = DocBin()
for text, ann in train_data:
    doc = nlp.make_doc(text)
    ents = []
    for start, end, label in ann["entities"]:
        # Use 'expand' to snap to the nearest token boundaries
        span = doc.char_span(start, end, label=label, alignment_mode="expand")
        if span is None:
            print(f"DEBUG: Mismatch in '{text}' for '{text[start:end]}'")
        else:
            ents.append(span)
    doc.ents = ents
    db.add(doc)

# 4. Use the proper Optimizer and Training Loop
optimizer = nlp.begin_training()
for i in range(50): # Increase epochs for small datasets
    random.shuffle(train_data)
    losses = {}
    for text, ann in train_data:
        # Create Example objects on the fly
        doc = nlp.make_doc(text)
        example = Example.from_dict(doc, ann)
        # Apply dropout to prevent overfitting
        nlp.update([example], drop=0.35, sgd=optimizer, losses=losses)
    if i % 10 == 0:
        print(f"Epoch {i} Loss: {losses}")

nlp.to_disk("theodore_ner")# ----------------------------

# ----------------------------
# Test
# ----------------------------
training_model = spacy.load("custom_ner_model")
print("Labels: \n", training_model.pipe_labels)

# Quick sanity check
test_text = "sync logs to gdrive:logs/app and upload config.json to s3:"
doc = training_model(test_text)
for ent in doc.ents:
    print(ent.text, ent.label_)
