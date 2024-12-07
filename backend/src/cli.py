# src/cli.py

import click
import time
from events import WebSocketEvent

class CLI:
    def __init__(self, message_queue):
        self.message_queue = message_queue
        self._last_event_name = None
        self._last_event_data = None

    def start_cli(self):
        print("WebSocket CLI started. Type 'exit' to quit.")

        while True:
            try:
                # Get event name input
                event_name = input("\nEnter event name (or 'exit' to quit): ").strip()

                if event_name.lower() == 'exit' or event_name.lower() == 'quit':
                    print("Exiting CLI...")
                    return

                # Get event data input
                event_data = input("Enter event data: ").strip()

                event = WebSocketEvent(event_name, event_data)

                # Debug print before putting on the queue
                print(f"\nSending event to queue:")
                print(f"  Name: {event.name}")
                print(f"  Data: {event.data}")

                # Put the event on the queue (instead of emitting directly)
                self.send_server_event(event.name, event.data)

                # Store last successful event
                self._last_event_name = event_name
                self._last_event_data = event_data

                # Confirmation message (event added to queue)
                print(f"✓ Event added to queue for processing")

                # Small delay to prevent flooding
                time.sleep(0.1)

            except KeyboardInterrupt:
                return
            except Exception as e:
                print(f"Error: {e}")

    def send_server_event(self, event_name, data, namespace=None):
        """
        Puts the event data onto the message queue.
        """
        message = {
            'event': event_name,
            'data': data,
            'namespace': namespace  # You can add namespace if needed
        }
        self.message_queue.put(message)