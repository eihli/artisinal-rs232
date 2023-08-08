int PIN_MEATBAG_IN = 2;
int PIN_MEATBAG_ACTIVATE = 3;

// MSG 0 and 1 are reserved for the low/high signals
// sent when meatbags are transcribing. 
int MSG_MEATBAG_DEACTIVATE = 2;
int MSG_MEATBAG_ACTIVATE = 3;
// Heartbeats every 0.5, 1.5, 2.5, etc... of cycle time. Heartbeats are when we tell the GUI to draw the rise/fall.
// Probes every 1, 2, 3, etc... of cycle time. Probes are when we tell the server what the bit was for that cycle.
int MSG_EVENT_HEARTBEAT = 4;
int MSG_EVENT_PROBE = 5;

int MEATBAG_BAUD = 4;
int CYCLE_TIMESPAN = 1000 / MEATBAG_BAUD;
int EVENT_TIMESPAN = CYCLE_TIMESPAN / 2;

int isMeatbagTranscribing = 0;
unsigned long previousTimestamp = 0;
unsigned long previousEvent = MSG_EVENT_PROBE;

void setup() {
  Serial.begin(9600);
  pinMode(PIN_MEATBAG_IN, INPUT);
  pinMode(PIN_MEATBAG_ACTIVATE, INPUT);
}

// It could be difficult to sync the timing of reading the input from the switch and
// displaying the signal on a graph. How do we get this loop and the Python/Matplotlib
// loop to be as in-sync as possible? And how can we sample in such a way that isn't
// vulnerable to slight mistakes?
//
// I think the key is going to be to probe the switch in the middle of the signal
// So, this loop will be the metronome. We'll send a "beat" message over Serial every
// 250, 500, 750, 1000 milliseconds (for example). And we'll send a "value" message
// every 125, 375, 625, 875 milliseconds.
void loop() {
  unsigned long currentTimestamp = millis();
  int timeElapsed = currentTimestamp - previousTimestamp;

  // Send the heartbeat every 125, 375, 625, etc...
  if (timeElapsed > EVENT_TIMESPAN 
      && previousEvent == MSG_EVENT_PROBE) 
  {
    previousTimestamp = currentTimestamp;
    previousEvent = MSG_EVENT_HEARTBEAT;
    Serial.print(MSG_EVENT_HEARTBEAT);
  } else 

  // Send the signal on every 250, 500, 750, etc...
  if (timeElapsed > EVENT_TIMESPAN 
      && previousEvent == MSG_EVENT_HEARTBEAT 
      && isMeatbagTranscribing == 1
      && timeElapsed > EVENT_TIMESPAN) 
  {
    previousTimestamp = currentTimestamp;
    previousEvent = MSG_EVENT_PROBE;
    int value = digitalRead(PIN_MEATBAG_IN);
    Serial.print(value);
  }

  // Meatbags have to eat and sleep. We don't want to drop the signal
  // during their moments of weakness. When meat fails, metal resumes control.
  int activate = digitalRead(PIN_MEATBAG_ACTIVATE);
  if (isMeatbagTranscribing == 1 && activate == LOW) {
    isMeatbagTranscribing = 0;
    Serial.print(MSG_MEATBAG_DEACTIVATE);
  } else if (isMeatbagTranscribing == 0 && activate == HIGH) {
    isMeatbagTranscribing = 1;
    Serial.print(MSG_MEATBAG_ACTIVATE);
  }
}
