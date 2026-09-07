/** Hot-seat "pass the device" curtain. The server withholds the seat's private data until acknowledged. */
export default function HotseatGate({ seat, onReady }: { seat: string; onReady: () => void }) {
  return (
    <div className="curtain" role="dialog" aria-modal="true">
      <h1>Pass the device to {seat}</h1>
      <p className="dim">Nothing private for {seat} is shown until they press the button.</p>
      <button className="primary" autoFocus onClick={onReady}>I am {seat} — show my hand</button>
    </div>
  );
}
