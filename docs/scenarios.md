# Scenarios

Scripted calls to walk through the agent, with the result to expect. They use the sample customers from [data-model.md](data-model.md#sample-customers), which are also built into the in-memory fallback store. Speak or type, whichever suits the situation.

Each scenario ends with a row in the Interactions tab. Check the row's `Outcome`, `Sentiment`, and `Caller Name`, and open the session in LiveKit Agent Insights using the row's `Room ID`.

## 1. Happy path, approved claim

| You | Agent |
| --- | --- |
| "Hi, I'd like to check on my claim." | Asks for the phone number linked to the account |
| "5550101001" | Greets you as Priya and asks for the PIN |
| "1234" | Thanks you, then reads the status: approved, payment scheduled within three business days. No documents needed |
| "No, that's all. Thanks." | Says goodbye and ends the call |

Record: `Priya Shah`, outcome `claim_status_provided`.

## 2. Documents required, in Hindi, with an interruption

Start in Hindi: "नमस्ते, मुझे अपने क्लेम का स्टेटस जानना है।"

1. Give `5550101002`, then PIN `4321`.
2. The agent says the claim is waiting for documents and starts explaining how to submit them, in Hindi.
3. **Interrupt** in the middle: "रुकिए, ईमेल का पता दोबारा बताइए।"

Expected: the agent stops speaking at once, keeps you verified (it does not ask for the PIN again), and answers. The voice stays Hindi.

Record: `Amit Verma`, outcome `claim_status_provided`, language `hi`.

## 3. Authentication failure

1. "I want my claim status." Give `5550101001`.
2. Say PIN `0000`. The agent says it did not match and allows one more try.
3. Say PIN `1111`.

Expected: the agent says it could not verify you, without saying why, and offers a representative. It shares no claim details and will not restart verification on this call.

Record: `Priya Shah (unverified)`, outcome `auth_failed`.

## 4. Customer not found

1. "Check my claim." Give `5559998888`. The agent asks you to check the number.
2. Give `5559997777`.

Expected: the agent says it could not find an account and offers a representative or the FAQ.

Record: `Unknown`, outcome `customer_not_found`.

## 5. Representative escalation

Say at any point, including before giving a number: "I want to talk to a person."

Expected: the agent arranges a callback right away, with no argument and no claim details shared if you were not verified.

Record: outcome `escalated`.

## 6. FAQ without verification

Ask: "What are your office hours?", "What's your mailing address?", "How do I start a new claim?", and "How does the claims process work?"

Expected: each answer matches [`agent/kb/faq.yaml`](../agent/kb/faq.yaml). Ask in Hindi and the Hindi answer is used.

Record: outcome `faq_answered`.

## 7. Emergency

During any step, say: "My father has chest pain right now."

Expected: the agent immediately tells you to hang up and call local emergency services (112 in India), then offers to help with the claim later. If verification was in progress it stops. No claim information is shared.

Record: outcome `emergency`, sentiment `distressed` when the summary is generated.

## 8. Unsupported question

Ask: "Can you tell me if my policy covers flood damage?"

Expected: a brief, polite statement that the agent cannot help with coverage questions, with an offer of the FAQ topics or a representative. It does not guess.

## 9. Language switching

Start in English, then say: "Please continue in Hindi." Then ask a question.

Expected: replies and the voice switch to Hindi. Say "English please" to switch back.

## 10. Typed input

Type your phone number and PIN into the message box instead of speaking them.

Expected: identical behavior to speaking. Typed emergency phrases are also caught.

## 11. Dropped call

Close the browser tab in the middle of a scenario.

Expected: a record is still written for the call, with the outcome reached so far.
