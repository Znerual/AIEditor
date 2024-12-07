# src/cli.py

import click
import time
from events import WebSocketEvent

class CLI:
    def __init__(self, socket_manager):
        self.socket_manager = socket_manager
        self._last_event_name = None
        self._last_event_data = None

    def start_cli(self):
        print("WebSocket CLI started. Type 'exit' to quit.")
        print("Available events: chat, text_change, custom_event")

        while True:
            try:
                 # Get event name input
                event_name = input("\nEnter event name (or 'exit' to quit): ").strip()
                
                if event_name.lower() == 'exit':
                    print("Exiting CLI...")
                    break
                
                # Get event data input
                event_data = input("Enter event data: ").strip()

                event = WebSocketEvent(event_name, event_data)

                 # Debug print before emission
                print(f"\nEmitting event:")
                print(f"  Name: {event.name}")
                print(f"  Data: {event.data}")

                self.socket_manager.emit_event(event)
                # Store last successful event
                self._last_event_name = event_name
                self._last_event_data = event_data
                
                # Confirmation message
                print(f"✓ Event sent successfully")
                
                # Small delay to prevent flooding
                time.sleep(0.1)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
