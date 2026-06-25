// background.js
console.log("Intel Background Worker Started");

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === "POST_DATA") {
        console.log("Background received POST_DATA:", request.url);
        fetch(request.url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request.data)
        })
        .then(res => res.json())
        .then(data => {
            console.log("Background fetch success:", data);
            sendResponse({success: true, data});
        })
        .catch(err => {
            console.error("Background fetch error:", err);
            sendResponse({success: false, error: err.toString()});
        });
        
        return true; // Keep the message channel open for async response
    }
    
    if (request.type === "GET_STATUS") {
        console.log("Background received GET_STATUS:", request.url);
        fetch(request.url)
        .then(res => res.json())
        .then(data => {
            console.log("Background GET_STATUS success:", data);
            sendResponse({success: true, data});
        })
        .catch(err => {
            console.error("Background GET_STATUS error:", err);
            sendResponse({success: false, error: err.toString()});
        });
        
        return true; // Keep the message channel open for async response
    }
});
