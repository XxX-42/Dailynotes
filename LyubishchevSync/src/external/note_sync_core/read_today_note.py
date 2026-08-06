import datetime
import subprocess
import sys

# [v1.0] Apple Notes Reader (Core)
# Uses AppleScript to interface with the Notes.app

class AppleNotesReader:
    _NOTE_SEPARATOR = chr(30)
    _FIELD_SEPARATOR = chr(31)

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

    @staticmethod
    def _escape_applescript(text):
        return str(text).replace('\\', '\\\\').replace('"', '\\"')

    def _to_html_body(self, content):
        safe_content = self._escape_applescript(content)
        return safe_content.replace('\n', '<br>')

    def list_notes_by_name(self, note_name):
        safe_name = self._escape_applescript(note_name)
        note_sep_id = ord(self._NOTE_SEPARATOR)
        field_sep_id = ord(self._FIELD_SEPARATOR)
        script = f'''
        tell application "Notes"
            set targetName to "{safe_name}"
            set foundNotes to every note whose name is targetName
            if (count of foundNotes) = 0 then
                return ""
            end if

            set noteSep to character id {note_sep_id}
            set fieldSep to character id {field_sep_id}
            set outputText to ""
            repeat with i from 1 to count of foundNotes
                set theNote to item i of foundNotes
                set outputText to outputText & (i as string) & fieldSep & (name of theNote as string) & fieldSep & (plaintext of theNote as string)
                if i is not (count of foundNotes) then
                    set outputText to outputText & noteSep
                end if
            end repeat
            return outputText
        end tell
        '''

        content, error = self._run_applescript(script)
        if error:
            if "UserCanceled" in error or "privilege" in error:
                print("⚠️  [Permission Denied] Please grant terminal/script access to Notes.")
            return []

        if not content:
            return []

        notes = []
        for note_chunk in content.split(self._NOTE_SEPARATOR):
            if not note_chunk:
                continue
            fields = note_chunk.split(self._FIELD_SEPARATOR, 2)
            if len(fields) != 3:
                continue
            try:
                index = int(fields[0])
            except ValueError:
                continue
            notes.append(
                {
                    "index": index,
                    "name": fields[1],
                    "plaintext": fields[2],
                }
            )
        return notes

    def _merge_note_plaintexts(self, notes):
        merged_lines = []
        seen = set()
        for note in notes:
            for raw_line in note.get("plaintext", "").splitlines():
                stripped = raw_line.strip()
                if not stripped:
                    continue
                if stripped in seen:
                    continue
                seen.add(stripped)
                merged_lines.append(raw_line.rstrip())
        return "\n".join(merged_lines)

    def get_note_content(self, note_name):
        """
        Retrieves the content (plaintext) of an Apple Note by its EXACT name.
        """
        notes = self.list_notes_by_name(note_name)
        if not notes:
            return None
        return notes[0].get("plaintext", "")

    def update_note_content(self, note_name, new_content):
        """
        [v4.0] Update the entire content of the note.
        Fixed: Converts newlines to <br> to prevent formatting loss (one-line mess).
        """
        safe_name = self._escape_applescript(note_name)
        html_body = self._to_html_body(new_content)
        
        script = f'''
        tell application "Notes"
            set targetName to "{safe_name}"
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
        existing_notes = self.list_notes_by_name(note_name)
        if existing_notes:
            return "EXISTS"

        safe_name = self._escape_applescript(note_name)
        html_body = self._to_html_body(body_content)
        
        script = f'''
        tell application "Notes"
            set targetName to "{safe_name}"
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
            return "FAILED"

        if resp == "CREATED":
            return "CREATED" if self.list_notes_by_name(note_name) else "FAILED"
        if resp == "EXISTS":
            return "EXISTS"
        return "FAILED"

    def _delete_duplicate_notes(self, note_name):
        safe_name = self._escape_applescript(note_name)
        script = f'''
        tell application "Notes"
            set targetName to "{safe_name}"
            set foundNotes to every note whose name is targetName
            if (count of foundNotes) <= 1 then
                return "UNCHANGED"
            end if

            repeat with idx from (count of foundNotes) to 2 by -1
                delete item idx of foundNotes
            end repeat
            return "DEDUPED"
        end tell
        '''

        resp, error = self._run_applescript(script)
        if error:
            print(f"❌ [AppleScript Error] Delete duplicate notes failed: {error}")
            return "FAILED"
        return resp or "FAILED"

    def dedupe_notes_by_name(self, note_name):
        notes = self.list_notes_by_name(note_name)
        if len(notes) <= 1:
            return "UNCHANGED"

        merged_content = self._merge_note_plaintexts(notes)
        if not self.update_note_content(note_name, merged_content):
            return "FAILED"

        delete_status = self._delete_duplicate_notes(note_name)
        if delete_status == "FAILED":
            return "FAILED"
        return "DEDUPED"

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
