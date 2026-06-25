// linkedin_jobs_ext/content.js
(function() {

class Config {
    static API_BASE = "http://localhost:8000/api/intel";
}

class State {
    constructor() {
        this.isAutoScrolling = false;
        this.userSkills = [];
        this.seenJobs = new Set();
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
                    console.log(`Jobs Scraper Sent post: ${postData.author} - ${postData.text_content.substring(0, 30)}...`);
                    resolve(response.data);
                } else {
                    console.error("Jobs Scraper Error:", response ? response.error : "No response");
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
        if (document.getElementById('intel-jobs-debug-box')) return;

        const debugBox = document.createElement('div');
        debugBox.id = 'intel-jobs-debug-box';
        debugBox.style.cssText = 'position:fixed;bottom:20px;left:20px;background:#0f172a;color:#10b981;padding:15px;border-radius:10px;z-index:999999;font-family:monospace;border:2px solid #10b981;box-shadow:0 0 10px rgba(0,0,0,0.5);';
        debugBox.innerHTML = `
            <b>Jobs Scraper Active</b><br/>
            Jobs Scraped: <span id="intel-jobs-count">0</span>
        `;
        document.body.appendChild(debugBox);
    }

    static updateCount(count) {
        const countSpan = document.getElementById('intel-jobs-count');
        if (countSpan) countSpan.innerText = count;
    }
}

class AutoScroller {
    constructor(state) {
        this.state = state;
        this.intervalId = null;
    }

    scrollFeed() {
        if (window.location.href.includes("/jobs")) {
            // Helper to get jobId from a card
            const getCardJobId = (card) => {
                let jobId = card.getAttribute('data-occludable-job-id') || card.getAttribute('data-job-id');
                if (!jobId) {
                    const link = card.querySelector('a[href*="/jobs/view/"]');
                    if (link) {
                        const match = link.href.match(/\/jobs\/view\/(\d+)/);
                        if (match) jobId = match[1];
                    }
                }
                return jobId;
            };

            const jobsList = document.querySelector('.scaffold-layout__list > div, .jobs-search-results-list, .jobs-search-results__list-container');
            
            if (jobsList) {
                // Find all job cards in the list
                const jobCards = document.querySelectorAll('.scaffold-layout__list [data-occludable-job-id], .jobs-search-results-list [data-occludable-job-id], [data-occludable-job-id], [class*="job-card-container"], [class*="job-card-list-item"]');
                
                // Find the first job card we haven't seen yet
                let targetCard = null;
                for (const card of jobCards) {
                    const jobId = getCardJobId(card);
                    if (jobId && !this.state.seenJobs.has(jobId)) {
                        targetCard = card;
                        break;
                    }
                }
                
                if (targetCard) {
                    console.log("Jobs AutoScroller: Clicking next unseen job card", targetCard);
                    // Scroll target card into view within the container
                    targetCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    
                    // Click the card (or the clickable title link inside it)
                    const clickTarget = targetCard.querySelector('a[href*="/jobs/view/"], a.job-card-list__title, [class*="job-card-list__title"]') || targetCard;
                    if (clickTarget) {
                        clickTarget.click();
                    }
                } else {
                    // If no unseen cards are loaded, scroll the container down to load more
                    console.log("Jobs AutoScroller: No unseen job cards on screen, scrolling down to load more...");
                    
                    // Check if we are near the bottom of the scroll container
                    const isAtBottom = jobsList.scrollTop + jobsList.clientHeight >= jobsList.scrollHeight - 50;
                    if (isAtBottom) {
                        // Try to find the Next Page button and click it!
                        const nextBtn = document.querySelector('button.artdeco-pagination__button--next, button[aria-label="Next"], [class*="pagination__button--next"], [aria-label*="Next page"]');
                        if (nextBtn && !nextBtn.disabled) {
                            console.log("Jobs AutoScroller: Reached list bottom. Clicking Next Page button...");
                            nextBtn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                            nextBtn.click();
                        } else {
                            console.log("Jobs AutoScroller: Reached list bottom but no enabled Next Page button found.");
                        }
                    } else {
                        jobsList.scrollBy(0, 400);
                    }
                }
                return;
            } else {
                // If there is no specific list scroll container (single-pane stack layout),
                // we can scroll the main window and click next page or unseen jobs in the viewport.
                const jobCards = document.querySelectorAll('[data-occludable-job-id], [data-job-id], [class*="job-card-container"], [class*="job-card-list-item"]');
                let targetCard = null;
                for (const card of jobCards) {
                    const jobId = getCardJobId(card);
                    if (jobId && !this.state.seenJobs.has(jobId)) {
                        targetCard = card;
                        break;
                    }
                }
                
                if (targetCard) {
                    console.log("Jobs AutoScroller (Window): Clicking next unseen job card", targetCard);
                    targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    const clickTarget = targetCard.querySelector('a[href*="/jobs/view/"], a.job-card-list__title, [class*="job-card-list__title"]') || targetCard;
                    if (clickTarget) {
                        clickTarget.click();
                    }
                } else {
                    console.log("Jobs AutoScroller (Window): Scrolling window down...");
                    window.scrollBy(0, 400);
                    
                    const isWinBottom = window.innerHeight + window.scrollY >= document.body.offsetHeight - 100;
                    if (isWinBottom) {
                        const nextBtn = document.querySelector('button.artdeco-pagination__button--next, button[aria-label="Next"], [class*="pagination__button--next"], [aria-label*="Next page"]');
                        if (nextBtn && !nextBtn.disabled) {
                            console.log("Jobs AutoScroller (Window): Reached page bottom. Clicking Next Page button...");
                            nextBtn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                            nextBtn.click();
                        }
                    }
                }
            }
        }
    }

    start() {
        if (this.intervalId) return;
        console.log("Jobs AutoScroller started");
        this.intervalId = setInterval(async () => {
            console.log("Jobs AutoScroller polling status...");
            try {
                const data = await NetworkClient.checkAutoScrollStatus();
                console.log("Jobs AutoScroller status received:", data);
                if (data && data.status === 'active') {
                    this.state.isAutoScrolling = true;
                    console.log("Jobs AutoScroller scrolling...");
                    this.scrollFeed();
                } else {
                    this.state.isAutoScrolling = false;
                }
            } catch (err) {
                console.error("Jobs AutoScroller poll error:", err);
            }
        }, 2000);
    }
}

class JobsObserver {
    constructor(state) {
        this.state = state;
        this.intervalId = null;
    }

    start() {
        if (this.intervalId) return;
        this.intervalId = setInterval(() => {
            if (!window.location.href.includes("/jobs")) return;
            
            const jobId = this.getJobId();
            if (!jobId) return;
            
            const skillsBox = document.getElementById('intel-job-skills-box');
            if (this.state.seenJobs.has(jobId) && skillsBox) return;

            this.processActiveJob(jobId);
        }, 1500);
    }

    getJobId() {
        const url = window.location.href;
        const matchView = url.match(/\/jobs\/view\/(\d+)/);
        if (matchView) return matchView[1];
        const matchSearch = url.match(/[?&]currentJobId=(\d+)/);
        if (matchSearch) return matchSearch[1];
        
        const activeCard = document.querySelector('.jobs-search-results-list__list-item--active, [class*="job-card-list--active"]');
        if (activeCard) {
            const jobIdAttr = activeCard.getAttribute('data-occludable-job-id') || activeCard.getAttribute('data-job-id');
            if (jobIdAttr) return jobIdAttr;
            const link = activeCard.querySelector('a[href*="/jobs/view/"]');
            if (link) {
                const linkMatch = link.href.match(/\/jobs\/view\/(\d+)/);
                if (linkMatch) return linkMatch[1];
            }
        }
        return null;
    }

    processActiveJob(jobId) {
        const titleNode = document.querySelector('.jobs-unified-top-card__job-title, .jobs-details-top-card__job-title, [class*="top-card__job-title"]');
        const companyNode = document.querySelector('.jobs-unified-top-card__company-name, .jobs-details-top-card__company-name, [class*="top-card__company-name"]');
        const descNode = document.querySelector('#job-details, .jobs-description__content, .jobs-description-content__text, [class*="jobs-description"]');
        
        if (!titleNode || !descNode) return;
        
        const title = titleNode.innerText.trim();
        const company = companyNode ? companyNode.innerText.trim().replace(/\n.*/s, '') : "Unknown Company";
        const description = descNode.innerText.trim();
        const jobUrl = `https://www.linkedin.com/jobs/view/${jobId}/`;

        const matchedSkills = [];
        if (this.state.userSkills && this.state.userSkills.length > 0) {
            const lowerDesc = description.toLowerCase();
            const lowerTitle = title.toLowerCase();
            for (const skill of this.state.userSkills) {
                const skillLower = skill.toLowerCase();
                const escapedSkill = skillLower.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                if (skillLower.length <= 4) {
                    const regex = new RegExp(`\\b${escapedSkill}\\b`, 'i');
                    if (regex.test(lowerDesc) || regex.test(lowerTitle)) {
                        matchedSkills.push(skill);
                    }
                } else {
                    if (lowerDesc.includes(skillLower) || lowerTitle.includes(skillLower)) {
                        matchedSkills.push(skill);
                    }
                }
            }
        }

        const topCard = document.querySelector('.jobs-unified-top-card, .jobs-details-top-card, [class*="details-top-card"], [class*="unified-top-card"]');
        
        const existingBox = document.getElementById('intel-job-skills-box');
        if (existingBox) {
            existingBox.remove();
        }

        if (topCard) {
            const skillBox = document.createElement('div');
            skillBox.id = 'intel-job-skills-box';
            skillBox.style.cssText = 'margin: 15px; padding: 12px; background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 8px; font-family: sans-serif; clear: both;';
            
            if (matchedSkills.length > 0) {
                skillBox.innerHTML = `
                    <div style="font-size: 11px; font-weight: bold; color: #10b981; margin-bottom: 6px; text-transform: uppercase; tracking-wider">Matched Resume Skills (${matchedSkills.length})</div>
                    <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                        ${matchedSkills.map(s => `<span style="background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">${s}</span>`).join('')}
                    </div>
                `;
            } else {
                skillBox.style.background = 'rgba(239, 68, 68, 0.08)';
                skillBox.style.border = '1px solid rgba(239, 68, 68, 0.25)';
                skillBox.innerHTML = `
                    <div style="font-size: 11px; font-weight: bold; color: #ef4444; text-transform: uppercase; tracking-wider">No matching resume skills found for this job</div>
                `;
            }
            
            topCard.appendChild(skillBox);
        }

        if (!this.state.seenJobs.has(jobId)) {
            this.state.seenJobs.add(jobId);
            IntelUI.updateCount(this.state.seenJobs.size);
            
            NetworkClient.sendPost({
                id: `linkedin_job_${jobId}`,
                author: company,
                text_content: `Job Title: ${title}\n\nDescription:\n${description}`,
                is_job_opportunity: 1,
                url: jobUrl,
                matched_skills: matchedSkills
            });
        }
    }
}

class AppController {
    constructor() {
        this.state = new State();
        this.jobsObserver = new JobsObserver(this.state);
        this.autoScroller = new AutoScroller(this.state);
        this.isInitialized = false;
    }

    initIntel() {
        if (this.isInitialized) return;
        console.log("LinkedIn Jobs Scraper Extension Active");
        IntelUI.injectDebugBox();
        this.jobsObserver.start();
        this.autoScroller.start();
        this.isInitialized = true;
    }

    checkAndInit() {
        if (window.location.href.includes("/jobs")) {
            if (!document.getElementById('intel-jobs-debug-box')) {
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
        console.log("LinkedIn Jobs Scraper Loaded!");
        
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
                    console.log(`Jobs Scraper loaded ${this.state.userSkills.length} user skills.`);
                }
            } catch(e) {
                console.error("Jobs Scraper failed to parse skills", e);
            }
        }
        
        this.checkAndInit();
        this.startNavigationObserver();
    }
}

const app = new AppController();
window.intelJobsApp = app;
app.run();

})();
