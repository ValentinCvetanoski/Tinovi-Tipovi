import { useEffect, useState } from "react";
import axios from "axios";

export default function App() {
  const [data, setData] = useState(null);

  useEffect(() => {
    axios
      .get("https://tinovi-tipovi.onrender.com/tips")
      .then((res) => setData(res.data));
  }, []);

  if (!data) return <p>POCEKAJ TRO IMAT REDICA EVROTIP</p>;

  const renderCategory = (title, list) => (
    <div style={{ marginBottom: "2rem" }}>
      <h2>{title}</h2>
      {list.length === 0 ? (
        <p>No tips available</p>
      ) : (
        <table border="1" cellPadding="6">
          <thead>
            <tr>
              <th>Match</th>
              <th>Kickoff</th>
              <th>Tip</th>
              <th>Odds</th>
            </tr>
          </thead>
          <tbody>
            {list.map((g, i) => (
              <tr key={i}>
                <td>{g.match}</td>
                <td>{g.kickoff}</td>
                <td>{g.tip}</td>
                <td>{g.odds.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );

  return (
    <div style={{ padding: "2rem" }}>
      <h1>Football Betting Tips</h1>
      {renderCategory("SIGURICI BATA", data.safe)}
      {renderCategory("OVA RIZICNO MALU", data.risky)}
      {renderCategory("NA GOLOJ A?", data.overunder)}
    </div>
  );
}
