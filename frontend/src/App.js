import React, { useState, useEffect } from "react";
import { getOrCreateUserId } from "./utils/user";
import "./App.css";

function App() {
  const [image, setImage] = useState(null);
  const [caption, setCaption] = useState("");
  const [text, setText] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [userId] = useState(getOrCreateUserId());
  const [showHistory, setShowHistory] = useState(false);

  const handleImageChange = (e) => {
    setImage(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!image) return;

    const formData = new FormData();
    formData.append("image", image);
    formData.append("userId", userId);

    setLoading(true);
    try {
      const response = await fetch("http://localhost:5000/analyze", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        setCaption(data.caption);
        setText(data.text);
        setImageUrl(data.imageUrl);
        fetchHistory();
      } else {
        alert(data.error || "Something went wrong");
      }
    } catch (error) {
      console.error("Error uploading image:", error);
      alert("Error connecting to backend");
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    try {
      const response = await fetch(
        `http://localhost:5000/history?userId=${userId}`
      );
      const data = await response.json();
      setHistory(data.reverse());
    } catch (error) {
      console.error("Failed to fetch history", error);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  return (
    <div className="app-container">
      <h1 className="title">SnapScan</h1>

      <div className="upload-form">
        <input type="file" onChange={handleImageChange} />
        <button className="upload-button" onClick={handleUpload}>
          Analyze Image
        </button>
        <button
          className="history-button"
          onClick={() => setShowHistory(!showHistory)}
        >
          {showHistory ? "Hide History" : "Show History"}
        </button>
      </div>

      {loading && <p className="loader">Processing image...</p>}

      {imageUrl && (
        <div className="result-container">
          <div className="image-box">
            <h3>Uploaded Image</h3>
            <img src={imageUrl} alt="Uploaded" />
          </div>
          <div className="analysis-box">
            <h3>Caption:</h3>
            <p>{caption}</p>
            <h3>Extracted Text:</h3>
            <pre>{text}</pre>
          </div>
        </div>
      )}

      {showHistory && (
        <div className="result-container" style={{ flexDirection: "column" }}>
          {history.map((item, idx) => (
            <div className="result-card" key={idx}>
              <img src={item.imageUrl} alt="" />
              <p>
                <strong>Caption:</strong> {item.caption}
              </p>
              <p>
                <strong>Text:</strong>
              </p>
              <pre>{item.text}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default App;
