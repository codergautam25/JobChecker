// background.js for LinkedIn Jobs Extension
console.log("Jobs Background Worker Started");

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === "POST_DATA") {
        console.log("Jobs Background received POST_DATA:", request.url);
        fetch(request.url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request.data)
        })
        .then(res => res.json())
        .then(data => {
            console.log("Jobs Background fetch success:", data);
            sendResponse({success: true, data});
        })
        .catch(err => {
            console.error("Jobs Background fetch error:", err);
            sendResponse({success: false, error: err.toString()});
        });
        
        return true; // Keep the message channel open for async response
    }
    
    if (request.type === "GET_STATUS") {
        console.log("Jobs Background received GET_STATUS:", request.url);
        fetch(request.url)
        .then(res => res.json())
        .then(data => {
            console.log("Jobs Background GET_STATUS success:", data);
            sendResponse({success: true, data});
        })
        .catch(err => {
            console.error("Jobs Background GET_STATUS error:", err);
            sendResponse({success: false, error: err.toString()});
        });
        
        return true; // Keep the message channel open for async response
    }
});
