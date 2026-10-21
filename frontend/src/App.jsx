import { useEffect, useState } from "react";

export default function App() {
  const [health, setHealth] = useState("checking...");

  useEffect(() => {
    fetch("/health")
      .then((response) => response.json())
      .then((data) => setHealth(`${data.status} (${data.service})`))
      .catch(() => setHealth("backend unreachable"));
  }, []);

  return (
    <main>
      <h1>URL Shortener</h1>
      <p>API status: {health}</p>
    </main>
  );
}