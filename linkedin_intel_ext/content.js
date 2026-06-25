// linkedin_intel_ext/content.js
(function() {

class Config {
    static API_BASE = "http://localhost:8000/api/intel";
}

class State {
    constructor() {
        this.seenPosts = new Set();
        this.processedNodes = new WeakSet();
        this.isAutoScrolling = false;
        this.userSkills = [];
    }
}

class NetworkClient {
    static sendPost(postData) {
        return new Promise((resolve) => {
            chrome.runtime.sendMessage({
                type: "POST_DATA",
                url: `${Config.API_BASE}/posts`,
                data: postData
            }, (response) => {
                if (response && response.success) {
                    console.log(`Sent post: ${postData.author} - ${postData.text_content.substring(0, 30)}...`);
                    resolve(response.data);
                } else {
                    console.error("Intel Ext Error:", response ? response.error : "No response");
                    resolve(null);
                }
            });
        });
    }

    static checkAutoScrollStatus() {
        return new Promise((resolve) => {
            chrome.runtime.sendMessage({
                type: "GET_STATUS",
                url: `${Config.API_BASE}/autoscroll/status`
            }, (response) => {
                if (response && response.success) {
                    resolve(response.data);
                } else {
                    resolve({ status: 'inactive' });
                }
            });
        });
    }

    static fetchProfile() {
        return new Promise((resolve) => {
            chrome.runtime.sendMessage({
                type: "GET_STATUS",
                url: `http://localhost:8000/api/profile`
            }, (response) => {
                if (response && response.success) {
                    resolve(response.data);
                } else {
                    resolve(null);
                }
            });
        });
    }
}

class IntelUI {
    static injectDebugBox() {
        if (document.getElementById('intel-debug-box')) return;

        const debugBox = document.createElement('div');
        debugBox.id = 'intel-debug-box';
        debugBox.style.cssText = 'position:fixed;bottom:20px;left:20px;background:#0f172a;color:#38bdf8;padding:15px;border-radius:10px;z-index:999999;font-family:monospace;border:2px solid #38bdf8;box-shadow:0 0 10px rgba(0,0,0,0.5);';
        debugBox.innerHTML = `
            <b>Intel Extension Active</b><br/>
            Posts Scraped: <span id="intel-count">0</span><br/>
            <button id="intel-dump-btn" style="margin-top:10px;background:#38bdf8;color:#0f172a;border:none;padding:5px 10px;cursor:pointer;border-radius:5px;font-weight:bold;">Analyze DOM (Check Console)</button>
        `;
        document.body.appendChild(debugBox);

        document.getElementById('intel-dump-btn').addEventListener('click', IntelUI.analyzeDOM);
    }

    static updateCount(count) {
        const countSpan = document.getElementById('intel-count');
        if (countSpan) countSpan.innerText = count;
    }

    static analyzeDOM() {
        console.log("==== AI DIAGNOSTIC REPORT ====");
        const allTextElements = Array.from(document.querySelectorAll('div, article, section, span, p')).filter(el => {
            return el.innerText && el.innerText.length > 50 && el.children.length === 0;
        });
        
        console.log(`Found ${allTextElements.length} deep text elements.`);
        
        allTextElements.slice(0, 5).forEach((el, idx) => {
            console.log(`\n--- Element ${idx} Preview: "${el.innerText.substring(0, 50)}..."`);
            let curr = el;
            let hierarchy = [];
            for(let i=0; i<8; i++) {
                if(!curr) break;
                let idStr = curr.id ? `#${curr.id}` : '';
                let attrStr = curr.hasAttribute('data-urn') ? `[data-urn=${curr.getAttribute('data-urn')}]` : '';
                let classStr = curr.className && typeof curr.className === 'string' ? `.${curr.className.split(' ').join('.')}` : '';
                hierarchy.push(`${curr.tagName.toLowerCase()}${idStr}${classStr}${attrStr}`);
                curr = curr.parentElement;
            }
            console.log(hierarchy.join('\n  ^ '));
        });
        console.log("===============================");
        alert("Check the Chrome F12 Console and copy the 'AI DIAGNOSTIC REPORT' to me!");
    }
}

class PostParser {
    constructor(state) {
        this.state = state;
    }

    processNode(postNode) {
        if (this.state.processedNodes.has(postNode)) return;
        this.state.processedNodes.add(postNode);

        let urnAttr = postNode.getAttribute('data-urn') || postNode.id || postNode.getAttribute('data-id');
        if (!urnAttr) {
            const uNode = postNode.querySelector('[componentkey]');
            if (uNode) urnAttr = uNode.getAttribute('componentkey');
        }

        const textBox = postNode.querySelector('[data-testid="expandable-text-box"], [componentkey^="feed-commentary"]');
        let textContent = "";
        let author = "Unknown Author";
        const fullText = postNode.innerText.trim();
        const lines = fullText.split('\n').map(l => l.trim()).filter(l => l.length > 0);

        if (textBox && textBox.innerText) {
            textContent = textBox.innerText.trim();
        } else {
            textContent = fullText;
        }

        const authorLink = postNode.querySelector('a[href*="/in/"], a[href*="/company/"]');
        if (authorLink) {
            author = authorLink.innerText.trim();
            if (!author || author.includes('\n')) {
                const img = authorLink.querySelector('img[alt*="profile"]');
                if (img) author = img.getAttribute('alt').replace('View ', '').replace('’s profile', '').replace("'s profile", '');
            }
        }
        
        if (!author || author.length < 2 || author === "Unknown Author") {
            if (lines.length > 0) author = lines[0];
        }
        
        if (author.includes('\n')) author = author.split('\n')[0];
        
        if (!urnAttr) {
            if (textContent.length > 10) {
                urnAttr = "pseudo_" + btoa(unescape(encodeURIComponent(author + textContent.substring(0,20)))).substring(0, 15);
            } else {
                return;
            }
        }
        
        if (this.state.seenPosts.has(urnAttr)) return;
        this.state.seenPosts.add(urnAttr);
        
        const keywords = ['hiring', 'job opportunity', 'looking for', 'we are hiring'];
        const isJobOpportunity = keywords.some(kw => textContent.toLowerCase().includes(kw));

        let postUrl = '';
        const permalinkNode = Array.from(postNode.querySelectorAll('a')).find(a => 
            a.href && (a.href.includes('/feed/update/urn:li:') || a.href.includes('/posts/'))
        );
        
        if (permalinkNode) {
            postUrl = permalinkNode.href.split('?')[0];
        } else {
            postUrl = `https://www.linkedin.com/feed/update/${urnAttr}/`;
            if (urnAttr.startsWith('pseudo_') || !urnAttr.includes('urn:li:')) {
                postUrl = authorLink ? authorLink.href : 'https://www.linkedin.com/feed/';
            }
        }

        const matchedSkills = [];
        if (this.state.userSkills && this.state.userSkills.length > 0) {
            const lowerText = textContent.toLowerCase();
            for (const skill of this.state.userSkills) {
                if (lowerText.includes(skill.toLowerCase())) {
                    matchedSkills.push(skill);
                }
            }
        }

        if (matchedSkills.length > 0) {
            const skillBox = document.createElement('div');
            skillBox.style.cssText = 'margin: 10px 16px; padding: 10px; background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 8px;';
            skillBox.innerHTML = `
                <div style="font-size: 12px; font-weight: bold; color: #0ea5e9; margin-bottom: 5px; text-transform: uppercase;">Matched Skills</div>
                <div style="display: flex; flex-wrap: wrap; gap: 5px;">
                    ${matchedSkills.map(s => `<span style="background: rgba(14, 165, 233, 0.15); color: #0284c7; border: 1px solid rgba(14, 165, 233, 0.3); padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">${s}</span>`).join('')}
                </div>
            `;
            postNode.appendChild(skillBox);
        }

        if (textContent && textContent.length > 5) {
            IntelUI.updateCount(this.state.seenPosts.size);
            NetworkClient.sendPost({
                id: urnAttr,
                author: author,
                text_content: textContent,
                is_job_opportunity: isJobOpportunity ? 1 : 0,
                url: postUrl,
                matched_skills: matchedSkills
            });
        }
    }
}

class AutoScroller {
    constructor(state) {
        this.state = state;
        this.intervalId = null;
    }

    scrollFeed() {
        // 1. Try scrolling the workspace main layout container
        const workspace = document.getElementById('workspace') || document.querySelector('main');
        if (workspace && workspace.scrollHeight > workspace.clientHeight) {
            workspace.scrollBy(0, 1000);
            return;
        }
        // 2. Try scrolling document.scrollingElement
        if (document.scrollingElement) {
            document.scrollingElement.scrollBy(0, 1000);
            return;
        }
        // 3. Fallback to window
        window.scrollBy(0, 1000);
    }

    start() {
        if (this.intervalId) return;
        console.log("AutoScroller started");
        this.intervalId = setInterval(async () => {
            console.log("AutoScroller polling status...");
            try {
                const data = await NetworkClient.checkAutoScrollStatus();
                console.log("AutoScroller status data received:", data);
                if (data && data.status === 'active') {
                    this.state.isAutoScrolling = true;
                    console.log("AutoScroller scrolling feed...");
                    this.scrollFeed();
                } else {
                    this.state.isAutoScrolling = false;
                }
            } catch (err) {
                console.error("AutoScroller poll error:", err);
            }
        }, 2000);
    }
}

class FeedObserver {
    constructor(postParser) {
        this.postParser = postParser;
        this.intervalId = null;
    }

    start() {
        if (this.intervalId) return;
        this.intervalId = setInterval(() => {
            if (!window.location.href.includes("/feed")) return;
            let posts = Array.from(document.querySelectorAll('main div[role="listitem"], main > div > div > section > div > div'));
            posts = posts.filter(el => el.querySelector('button[aria-label*="Like"], [data-testid="expandable-text-box"], [componentkey^="feed-commentary"]'));
            posts = posts.filter(post => !posts.some(parent => parent !== post && parent.contains(post)));
            
            posts.forEach(post => this.postParser.processNode(post));
        }, 2000);
    }
}



class AppController {
    constructor() {
        this.state = new State();
        this.postParser = new PostParser(this.state);
        this.feedObserver = new FeedObserver(this.postParser);
        this.autoScroller = new AutoScroller(this.state);
        this.isInitialized = false;
    }

    initIntel() {
        if (this.isInitialized) return;
        console.log("LinkedIn Intel Extension Active");
        IntelUI.injectDebugBox();
        this.feedObserver.start();
        this.autoScroller.start();
        this.isInitialized = true;
    }

    checkAndInit() {
        if (window.location.href.includes("/feed")) {
            if (!document.getElementById('intel-debug-box')) {
                // If it was removed but we are initialized, just re-inject
                IntelUI.injectDebugBox();
            }
            this.initIntel();
        }
    }

    startNavigationObserver() {
        let lastUrl = location.href;
        new MutationObserver(() => {
            const url = location.href;
            if (url !== lastUrl) {
                lastUrl = url;
                setTimeout(() => this.checkAndInit(), 500);
            }
        }).observe(document, { subtree: true, childList: true });

        setInterval(() => this.checkAndInit(), 2000);
    }

    async run() {
        console.log("LinkedIn Intel Extension v4 Modular Loaded!");
        
        // Fetch user profile and extract skills
        const data = await NetworkClient.fetchProfile();
        if (data && data.profile && data.profile.skills) {
            try {
                let parsedSkills = data.profile.skills;
                if (typeof parsedSkills === 'string' && parsedSkills.startsWith('[')) {
                    parsedSkills = JSON.parse(parsedSkills);
                }
                if (Array.isArray(parsedSkills)) {
                    this.state.userSkills = parsedSkills.filter(s => s && s.trim());
                    console.log(`Loaded ${this.state.userSkills.length} user skills for matching.`);
                }
            } catch(e) {
                console.error("Failed to parse skills", e);
            }
        }
        
        this.checkAndInit();
        this.startNavigationObserver();
    }
}

// Bootstrap the application
const app = new AppController();
window.intelApp = app;
app.run();

})();
