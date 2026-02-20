import time
import sys
sys.path.insert(0, "/Users/user999/Documents/【Liang_project】/Code_Scripits/2025_DailynoteSync_complete_beta/AntigravitySync/src")
from external.note_sync_core.reader import AppleNotesReader

reader = AppleNotesReader(None)
import datetime

today = datetime.date.today()
note_name = f"{today.year}/{today.month}/{today.day}"

print("Reading...")
c1 = reader.get_note_content(note_name)
print("Hash 1:", hash(c1))

print("Please quickly modify the note in Apple Notes and save within 5 seconds...")
time.sleep(5)

c2 = reader.get_note_content(note_name)
print("Hash 2:", hash(c2))
if c1 == c2:
    print("WARNING: AppleScript returned EXACTLY the same string even after edit!")
else:
    print("Success: AppleScript returned new content:", repr(c2[-20:]))

