import React, { useState } from "react";
import axios from "axios";

const GoogleSearch = () => {
    const [query, setQuery] = useState("");
    const [apiKey, setApiKey] = useState("");
    const [cx, setCx] = useState("");
    const [results, setResults] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);

    const handleSearch = async () => {
        setLoading(true);
        try {
            const res = await axios.get("/api/search", {
                params: {
                    q: query,
                    api_key: apiKey,
                    cx: cx,
                    num: 5,
                },
            });
            setResults(res.data.results || []);
        } catch (e) {
            alert("검색 실패: " + e);
        }
        setLoading(false);
    };

    return (
        <div>
            <input
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Google API Key"
            />
            <input
                value={cx}
                onChange={(e) => setCx(e.target.value)}
                placeholder="Custom Search Engine ID"
            />
            <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="검색어"
            />
            <button onClick={handleSearch} disabled={loading}>
                검색
            </button>
            <ul>
                {results.map((item, idx) => (
                    <li key={idx}>
                        <a
                            href={item.link}
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            {item.title}
                        </a>
                        <p>{item.snippet}</p>
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default GoogleSearch;
