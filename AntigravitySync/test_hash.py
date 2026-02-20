# Let's simulate the loop
import difflib

old = "A\nB\n"
new = "A\nB"

diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(), n=0, lineterm=''))
print("Diff:", len(diff))

