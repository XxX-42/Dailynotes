import objc
import threading
import time
import datetime
from EventKit import EKEventStore, EKEntityTypeReminder
from Foundation import NSPredicate, NSDate

# 0 = Event, 1 = Reminder
ENTITY_TYPE_REMINDER = 1

class ReminderTest:
    def __init__(self):
        self.store = EKEventStore.alloc().init()
        self.access_granted = False

    def check_access(self):
        group = threading.Event()
        
        def callback(granted, error):
            self.access_granted = granted
            if error:
                print(f"❌ Error: {error}")
            group.set()

        status = EKEventStore.authorizationStatusForEntityType_(ENTITY_TYPE_REMINDER)
        print(f"Current Status: {status}")

        if hasattr(self.store, 'requestFullAccessToRemindersWithCompletion_'):
             self.store.requestFullAccessToRemindersWithCompletion_(callback)
        else:
             self.store.requestAccessToEntityType_completion_(ENTITY_TYPE_REMINDER, callback)
        
        group.wait()
        return self.access_granted

    def fetch_reminders(self):
        if not self.access_granted:
            print("No access")
            return

        print("Fetching reminders...")
        # Predicate for all reminders (incomplete)
        # For reminders, we use fetchRemindersMatchingPredicate_completion_ which is async!
        
        # Or sync method? fetchRemindersMatchingPredicate is NOT available.
        # We MUST use the async method.
        
        predicate = self.store.predicateForRemindersInCalendars_(None) # None = all calendars
        
        group = threading.Event()
        
        def fetch_callback(reminders):
            print(f"✅ Fetched {len(reminders) if reminders else 0} reminders.")
            if reminders:
                for r in reminders[:5]:
                    print(f" - [{r.title()}] Completed: {r.isCompleted()}")
            group.set()
            
        self.store.fetchRemindersMatchingPredicate_completion_(predicate, fetch_callback)
        group.wait()

if __name__ == "__main__":
    test = ReminderTest()
    if test.check_access():
        print("Access Granted")
        test.fetch_reminders()
    else:
        print("Access Denied")
