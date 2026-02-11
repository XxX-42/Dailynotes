
import subprocess
import datetime
import sys

# [v1.0] Apple Notes Reader (Core)
# Uses AppleScript to interface with the Notes.app

class AppleNotesReader:
    def __init__(self):
        pass

    def _run_applescript(self, script_content):
        """
        Runs AppleScript using osascript (subprocess).
        """
        try:
            # -e is for one-liner, but for block we pipe into stdin
            process = subprocess.Popen(
                ['osascript'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=script_content)
            
            if process.returncode != 0:
                # If permission denied or other OSA error
                return None, stderr.strip()
            return stdout.strip(), None
            
        except Exception as e:
            return None, str(e)

    def get_note_content(self, note_name):
        """
        Retrieves the content (plaintext) of an Apple Note by its EXACT name.
        """
        # AppleScript Logic:
        # 1. Target Note by Name
        # 2. Return 'plaintext' (content without HTML tags)
        # 3. Return "NOT_FOUND" if list is empty
        
        script = f'''
        tell application "Notes"
            set targetName to "{note_name}"
            
            -- Try to find the note by exact name
            set foundNotes to every note whose name is targetName
            
            if (count of foundNotes) > 0 then
                set theNote to item 1 of foundNotes
                return plaintext of theNote
            else
                return "NOT_FOUND"
            end if
        end tell
        '''
        
        content, error = self._run_applescript(script)
        
        if error:
            # Handle user permissions or missing app errors
            if "UserCanceled" in error or "privilege" in error:
                print(f"⚠️  [Permission Denied] Please grant terminal/script access to Notes.")
            return None
            
        if content == "NOT_FOUND":
            return None
            
        return content

    def update_note_content(self, note_name, new_content):
        """
        [v4.0] Update the entire content of the note.
        Fixed: Converts newlines to <br> to prevent formatting loss (one-line mess).
        """
        # 1. Escape special chars for AppleScript string
        safe_content = new_content.replace('\\', '\\\\').replace('"', '\\"')
        
        # 2. Convert newlines to HTML breaks for Notes body
        html_body = safe_content.replace('\n', '<br>')
        
        script = f'''
        tell application "Notes"
            set targetName to "{note_name}"
            set foundNotes to every note whose name is targetName
            
            if (count of foundNotes) > 0 then
                set theNote to item 1 of foundNotes
                set body of theNote to "{html_body}"
                return "OK"
            else
                return "NOT_FOUND"
            end if
        end tell
        '''
        
        resp, error = self._run_applescript(script)
        if error:
            print(f"❌ [AppleScript Error] Update failed: {error}")
            return False
            
        return resp == "OK"

    def create_note(self, note_name, body_content=""):
        """
        [v4.1] Create a new note if it doesn't exist.
        """
        # Escape content
        safe_content = body_content.replace('\\', '\\\\').replace('"', '\\"')
        html_body = safe_content.replace('\n', '<br>')
        
        script = f'''
        tell application "Notes"
            -- Check if exists first to avoid duplicates
            set targetName to "{note_name}"
            set foundNotes to every note whose name is targetName
            
            if (count of foundNotes) = 0 then
                make new note with properties {{name:targetName, body:"{html_body}"}}
                return "CREATED"
            else
                return "EXISTS"
            end if
        end tell
        '''
        
        resp, error = self._run_applescript(script)
        if error:
            print(f"❌ [AppleScript Error] Create note failed: {error}")
            return False
            
        return resp == "CREATED"

if __name__ == "__main__":
    # Self-test logic
    reader = AppleNotesReader()
    
    today = datetime.date.today()
    # Format: yyyy/m/d (e.g. 2026/2/11) - No zero padding
    today_str = f"{today.year}/{today.month}/{today.day}"
    
    print(f"🔎 [Test] Attempting to read note: '{today_str}'")
    
    content = reader.get_note_content(today_str)
    
    if content:
        print(f"✅ [Success] Read {len(content)} chars.")
        print("="*40)
        print(content)
        print("="*40)
    else:
        print(f"❌ [Failed] Note '{today_str}' not found or empty.")
        print("   (Ensure a note with this EXACT title exists in Apple Notes)")
