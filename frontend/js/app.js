/**
 * Student Resume Analyzer — Client Application Script
 *
 * Responsibilities:
 * 1. Health check verification against GET /health.
 * 2. File input validation (extension, size <= 5 MB).
 * 3. Multipart upload to POST /api/v1/resumes/extract with loading indicator.
 * 4. Trigger structured analysis via POST /api/v1/resumes/analyze-text.
 * 5. Display contact coordinates, detected sections, and canonical skills.
 * 6. Volatile in-memory state management: NO localStorage, sessionStorage,
 *    cookies, or persistent storage of candidate resumes.
 * 7. Explicit state clearing.
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const indicator = document.getElementById("status-indicator");
  const statusText = document.getElementById("status-text");

  const fileInput = document.getElementById("resume-file");
  const dropzoneText = document.getElementById("dropzone-filename");
  const extractBtn = document.getElementById("extract-btn");
  const analyzeStructureBtn = document.getElementById("analyze-structure-btn");
  const clearBtn = document.getElementById("clear-btn");
  const loadingState = document.getElementById("loading-state");
  const loadingText = document.getElementById("loading-text");

  const errorBanner = document.getElementById("error-banner");
  const errorMessage = document.getElementById("error-message");

  const resultsPlaceholder = document.getElementById("results-placeholder");
  const resultsContent = document.getElementById("results-content");

  const metricPages = document.getElementById("metric-pages");
  const metricWords = document.getElementById("metric-words");
  const metricChars = document.getElementById("metric-chars");
  const metricEngine = document.getElementById("metric-engine");
  const docName = document.getElementById("doc-name");
  const statusPill = document.getElementById("status-pill");

  const structuredBox = document.getElementById("structured-box");
  const contactGrid = document.getElementById("contact-grid");
  const sectionPills = document.getElementById("section-pills");
  const skillsContainer = document.getElementById("skills-container");
  const skillCountSpan = document.getElementById("skill-count");

  const warningsBox = document.getElementById("warnings-box");
  const warningsList = document.getElementById("warnings-list");
  const extractedTextArea = document.getElementById("extracted-text-area");
  const copyBtn = document.getElementById("copy-btn");

  // Step 2 & Matching Elements
  const jobDescriptionInput = document.getElementById("job-description");
  const matchBtn = document.getElementById("match-btn");
  const matchingResultsCard = document.getElementById("matching-results-card");
  const textSimVal = document.getElementById("text-sim-val");
  const skillOverlapVal = document.getElementById("skill-overlap-val");
  const skillOverlapDesc = document.getElementById("skill-overlap-desc");
  const matchedCount = document.getElementById("matched-count");
  const matchedSkillsChips = document.getElementById("matched-skills-chips");
  const missingCount = document.getElementById("missing-count");
  const missingSkillsChips = document.getElementById("missing-skills-chips");
  const additionalCount = document.getElementById("additional-count");
  const additionalSkillsChips = document.getElementById("additional-skills-chips");

  // Phase 8: Heuristic Feedback Elements
  const feedbackBtn = document.getElementById("feedback-btn");
  const feedbackBox = document.getElementById("feedback-box");
  const feedbackTotalScore = document.getElementById("feedback-total-score");
  const feedbackTierBadge = document.getElementById("feedback-tier-badge");
  const feedbackRecommendationsList = document.getElementById("feedback-recommendations-list");

  const dimStructureScore = document.getElementById("dim-structure-score");
  const dimStructureStatus = document.getElementById("dim-structure-status");
  const dimStructureSummary = document.getElementById("dim-structure-summary");
  const dimStructureEvidence = document.getElementById("dim-structure-evidence");

  const dimContactScore = document.getElementById("dim-contact-score");
  const dimContactStatus = document.getElementById("dim-contact-status");
  const dimContactSummary = document.getElementById("dim-contact-summary");
  const dimContactEvidence = document.getElementById("dim-contact-evidence");

  const dimImpactScore = document.getElementById("dim-impact-score");
  const dimImpactStatus = document.getElementById("dim-impact-status");
  const dimImpactSummary = document.getElementById("dim-impact-summary");
  const dimImpactEvidence = document.getElementById("dim-impact-evidence");

  const dimSkillsScore = document.getElementById("dim-skills-score");
  const dimSkillsStatus = document.getElementById("dim-skills-status");
  const dimSkillsSummary = document.getElementById("dim-skills-summary");
  const dimSkillsEvidence = document.getElementById("dim-skills-evidence");

  const recognizedMetricsSubcard = document.getElementById("recognized-metrics-subcard");
  const recognizedMetricsCount = document.getElementById("recognized-metrics-count");
  const metricsSnippetsList = document.getElementById("metrics-snippets-list");

  // In-memory session state (strictly volatile)
  let activeFile = null;
  let activeExtractedText = "";
  let activeExtractionResult = null;
  let activeStructuredResult = null;
  let activeMatchResult = null;
  let activeFeedbackResult = null;

  // 1. Health check
  async function checkBackendHealth() {
    try {
      const response = await fetch("/health");
      if (response.ok) {
        const data = await response.json();
        if (data.status === "ok") {
          indicator.className = "status-indicator connected";
          statusText.textContent = `Backend Online (v${data.version})`;
          return;
        }
      }
      throw new Error(`HTTP ${response.status}`);
    } catch (err) {
      indicator.className = "status-indicator error";
      statusText.textContent = "Backend Offline / Unreachable";
    }
  }

  // Error handling helpers
  function showError(msg) {
    errorMessage.textContent = msg;
    errorBanner.classList.remove("hidden");
  }

  function hideError() {
    errorBanner.classList.add("hidden");
    errorMessage.textContent = "";
  }

  // 2. File Selection Handler
  fileInput.addEventListener("change", (e) => {
    hideError();
    const files = e.target.files;
    if (!files || files.length === 0) {
      resetSession();
      return;
    }

    const file = files[0];

    // Client-side extension check
    const lowerName = file.name.toLowerCase();
    if (lowerName.endsWith(".doc")) {
      showError("Legacy binary Word documents (.doc) are not supported. Please save or convert your resume to modern Word (.docx) or PDF (.pdf) format.");
      fileInput.value = "";
      extractBtn.disabled = true;
      analyzeStructureBtn.disabled = true;
      feedbackBtn.disabled = true;
      matchBtn.disabled = true;
      return;
    }

    if (!lowerName.endsWith(".pdf") && !lowerName.endsWith(".docx")) {
      showError("Selected file is not supported. Please upload a PDF (.pdf) or Word (.docx) document.");
      fileInput.value = "";
      extractBtn.disabled = true;
      analyzeStructureBtn.disabled = true;
      feedbackBtn.disabled = true;
      matchBtn.disabled = true;
      return;
    }

    // Client-side size check (5 MB)
    const maxBytes = 5 * 1024 * 1024;
    if (file.size > maxBytes) {
      showError(`File size exceeds 5 MB limit (${(file.size / (1024 * 1024)).toFixed(2)} MB).`);
      fileInput.value = "";
      extractBtn.disabled = true;
      analyzeStructureBtn.disabled = true;
      return;
    }

    if (file.size === 0) {
      showError("The selected file is empty (0 bytes).");
      fileInput.value = "";
      extractBtn.disabled = true;
      analyzeStructureBtn.disabled = true;
      return;
    }

    activeFile = file;
    dropzoneText.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    extractBtn.disabled = false;
    clearBtn.classList.remove("hidden");
  });

  // 3. Step 1: Extract Text Action
  extractBtn.addEventListener("click", async () => {
    if (!activeFile) return;

    hideError();
    extractBtn.disabled = true;
    loadingText.textContent = "Extracting text from document in memory...";
    loadingState.classList.remove("hidden");

    const formData = new FormData();
    formData.append("file", activeFile);

    try {
      const response = await fetch("/api/v1/resumes/extract", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Extraction failed with HTTP ${response.status}`);
      }

      // Store volatile in-memory extraction
      activeExtractionResult = data;
      activeExtractedText = data.extracted_text || "";
      renderExtractionResult(data);

      if (activeExtractedText.trim().length > 0) {
        analyzeStructureBtn.disabled = false;
        feedbackBtn.disabled = false;
        if (jobDescriptionInput.value.trim().length > 0) {
          matchBtn.disabled = false;
        }
      }
    } catch (err) {
      showError(err.message || "An error occurred while communicating with the extraction service.");
      extractBtn.disabled = false;
      analyzeStructureBtn.disabled = true;
      feedbackBtn.disabled = true;
      matchBtn.disabled = true;
    } finally {
      loadingState.classList.add("hidden");
    }
  });

  // Monitor Job Description textarea input
  jobDescriptionInput.addEventListener("input", () => {
    const hasResume = activeExtractedText.trim().length > 0;
    const hasJd = jobDescriptionInput.value.trim().length > 0;
    matchBtn.disabled = !(hasResume && hasJd);
  });

  // 4. Render Raw Extraction Metrics
  function renderExtractionResult(data) {
    metricPages.textContent = data.page_count;
    metricWords.textContent = data.word_count.toLocaleString();
    metricChars.textContent = data.character_count.toLocaleString();
    metricEngine.textContent = data.parser_engine || "Default";
    docName.textContent = data.filename;

    if (data.is_scanned_or_image_based || data.warnings.length > 0) {
      statusPill.className = "status-pill warning";
      statusPill.textContent = data.is_scanned_or_image_based ? "Image / Scanned" : "Warning";
    } else {
      statusPill.className = "status-pill";
      statusPill.textContent = "Extracted";
    }

    renderWarnings(data.warnings);

    extractedTextArea.value = data.extracted_text || "(No text could be extracted from document)";

    resultsPlaceholder.classList.add("hidden");
    resultsContent.classList.remove("hidden");
    extractBtn.disabled = false;
  }

  // 5. Step 2: Run Structured Analysis Action
  analyzeStructureBtn.addEventListener("click", async () => {
    if (!activeExtractedText.trim()) {
      showError("No extracted text available for analysis. Please extract text first.");
      return;
    }

    hideError();
    analyzeStructureBtn.disabled = true;
    loadingText.textContent = "Detecting sections and matching skills...";
    loadingState.classList.remove("hidden");

    try {
      const payload = {
        text: activeExtractedText,
        filename: activeFile ? activeFile.name : "resume.pdf",
      };

      const response = await fetch("/api/v1/resumes/analyze-text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Structured parsing failed with HTTP ${response.status}`);
      }

      activeStructuredResult = data;
      renderStructuredResult(data);
    } catch (err) {
      showError(err.message || "An error occurred during structured resume analysis.");
    } finally {
      loadingState.classList.add("hidden");
      analyzeStructureBtn.disabled = false;
    }
  });

  // 6. Render Structured Entities (Contact, Sections, Skills)
  function renderStructuredResult(data) {
    // A. Contact Information
    contactGrid.innerHTML = "";
    const contactFields = [
      { label: "Email", val: data.contact_info.email, isLink: false },
      { label: "Phone", val: data.contact_info.phone, isLink: false },
      { label: "LinkedIn", val: data.contact_info.linkedin_url, isLink: true },
      { label: "GitHub", val: data.contact_info.github_url, isLink: true },
      { label: "Portfolio", val: data.contact_info.portfolio_url, isLink: true },
    ];

    contactFields.forEach((f) => {
      const div = document.createElement("div");
      div.className = "contact-item";

      const label = document.createElement("span");
      label.className = "contact-label";
      label.textContent = f.label;
      div.appendChild(label);

      const val = document.createElement("span");
      val.className = "contact-val";

      if (f.val) {
        if (f.isLink) {
          const a = document.createElement("a");
          a.href = f.val;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          a.textContent = f.val;
          val.appendChild(a);
        } else {
          val.textContent = f.val;
        }
      } else {
        val.textContent = "Not detected";
        val.style.color = "#94a3b8";
      }

      div.appendChild(val);
      contactGrid.appendChild(div);
    });

    // B. Sections Overview
    sectionPills.innerHTML = "";
    const canonicalSections = [
      "Summary",
      "Education",
      "Experience",
      "Projects",
      "Skills",
      "Certifications",
      "Achievements",
      "Extracurricular",
    ];

    canonicalSections.forEach((secName) => {
      const key = secName.toLowerCase();
      const isFound = data.detected_section_keys.includes(key);

      const pill = document.createElement("span");
      pill.className = `sec-pill ${isFound ? "found" : "missing"}`;
      pill.textContent = `${isFound ? "✓" : "—"} ${secName}`;
      sectionPills.appendChild(pill);
    });

    // C. Technical Skills
    skillsContainer.innerHTML = "";
    skillCountSpan.textContent = data.skills.length;

    if (Object.keys(data.skills_by_category).length === 0) {
      const emptyNote = document.createElement("p");
      emptyNote.style.fontSize = "0.82rem";
      emptyNote.style.color = "#94a3b8";
      emptyNote.textContent = "No canonical technical skills from standard taxonomy detected.";
      skillsContainer.appendChild(emptyNote);
    } else {
      for (const [category, skillNames] of Object.entries(data.skills_by_category)) {
        const group = document.createElement("div");
        group.className = "skill-category-group";

        const title = document.createElement("div");
        title.className = "skill-category-title";
        title.textContent = `${category} (${skillNames.length}):`;
        group.appendChild(title);

        const chips = document.createElement("div");
        chips.className = "skill-chips";

        skillNames.forEach((name) => {
          const chip = document.createElement("span");
          chip.className = "skill-chip";
          chip.textContent = name;
          chips.appendChild(chip);
        });

        group.appendChild(chips);
        skillsContainer.appendChild(group);
      }
    }

    // D. Warnings & Status
    renderWarnings(data.warnings);

    statusPill.className = "status-pill";
    statusPill.textContent = "Fully Analyzed";

    structuredBox.classList.remove("hidden");
  }

  function renderWarnings(warnings) {
    warningsList.innerHTML = "";
    if (warnings && warnings.length > 0) {
      warnings.forEach((warn) => {
        const li = document.createElement("li");
        li.textContent = warn;
        warningsList.appendChild(li);
      });
      warningsBox.classList.remove("hidden");
    } else {
      warningsBox.classList.add("hidden");
    }
  }

  // 7. Step 3: Run Job Matching Action
  matchBtn.addEventListener("click", async () => {
    const resumeText = activeExtractedText.trim();
    const jdText = jobDescriptionInput.value.trim();

    if (!resumeText) {
      showError("No resume text available. Please extract a resume document (.pdf or .docx) first.");
      return;
    }

    if (!jdText) {
      showError("Please enter or paste a job description.");
      return;
    }

    if (jdText.length > 50000) {
      showError("Job description exceeds the 50,000 character limit.");
      return;
    }

    hideError();
    matchBtn.disabled = true;
    loadingText.textContent = "Computing lexical similarity & skill overlap...";
    loadingState.classList.remove("hidden");

    try {
      const payload = {
        resume_text: resumeText,
        job_description: jdText,
        resume_filename: activeFile ? activeFile.name : null,
      };

      const response = await fetch("/api/v1/resumes/match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Matching failed with HTTP ${response.status}`);
      }

      activeMatchResult = data;
      renderMatchResult(data);
    } catch (err) {
      showError(err.message || "An error occurred during job description matching.");
    } finally {
      loadingState.classList.add("hidden");
      matchBtn.disabled = false;
    }
  });

  // 8. Render Matching Results (Similarity & Skill Overlap)
  function renderMatchResult(data) {
    // A. Text similarity
    const simPct = (data.text_similarity * 100).toFixed(1);
    textSimVal.textContent = `${simPct}%`;

    // B. Skill overlap
    if (data.skill_overlap_ratio !== null && data.skill_overlap_ratio !== undefined) {
      const overlapPct = (data.skill_overlap_ratio * 100).toFixed(1);
      skillOverlapVal.textContent = `${overlapPct}%`;
    } else {
      skillOverlapVal.textContent = "N/A";
    }
    skillOverlapDesc.textContent = data.skill_overlap_explanation || "Ratio of recognized JD skills detected on resume.";

    // C. Matched skills
    matchedCount.textContent = data.matched_skills.length;
    matchedSkillsChips.innerHTML = "";
    if (data.matched_skills.length === 0) {
      const emptySpan = document.createElement("span");
      emptySpan.className = "skill-chip chip-empty";
      emptySpan.textContent = "No skills matched";
      matchedSkillsChips.appendChild(emptySpan);
    } else {
      data.matched_skills.forEach((skill) => {
        const chip = document.createElement("span");
        chip.className = "skill-chip chip-matched";
        chip.textContent = skill;
        matchedSkillsChips.appendChild(chip);
      });
    }

    // D. Missing skills (in JD, not detected in resume)
    missingCount.textContent = data.missing_skills.length;
    missingSkillsChips.innerHTML = "";
    if (data.missing_skills.length === 0) {
      const emptySpan = document.createElement("span");
      emptySpan.className = "skill-chip chip-empty";
      const jdSkillsCount = (data.job_description_skills || []).length;
      emptySpan.textContent = jdSkillsCount === 0
        ? "No recognized skills in job description"
        : "None (all recognized JD skills detected)";
      missingSkillsChips.appendChild(emptySpan);
    } else {
      data.missing_skills.forEach((skill) => {
        const chip = document.createElement("span");
        chip.className = "skill-chip chip-missing";
        chip.textContent = skill;
        missingSkillsChips.appendChild(chip);
      });
    }

    // E. Additional skills (in resume, not mentioned in JD)
    additionalCount.textContent = data.additional_skills.length;
    additionalSkillsChips.innerHTML = "";
    if (data.additional_skills.length === 0) {
      const emptySpan = document.createElement("span");
      emptySpan.className = "skill-chip chip-empty";
      emptySpan.textContent = "None";
      additionalSkillsChips.appendChild(emptySpan);
    } else {
      data.additional_skills.forEach((skill) => {
        const chip = document.createElement("span");
        chip.className = "skill-chip chip-additional";
        chip.textContent = skill;
        additionalSkillsChips.appendChild(chip);
      });
    }

    matchingResultsCard.classList.remove("hidden");
  }

  // 9. Step 3: Heuristic Feedback Rubric Action
  feedbackBtn.addEventListener("click", async () => {
    const resumeText = activeExtractedText.trim() || extractedTextArea.value.trim();
    if (!resumeText) {
      showError("Please extract a resume first or ensure the extracted text area is populated.");
      return;
    }

    if (resumeText.length > 50000) {
      showError("Resume text exceeds the 50,000 character limit.");
      return;
    }

    const jdText = jobDescriptionInput.value.trim();
    if (jdText && jdText.length > 50000) {
      showError("Job description exceeds the 50,000 character limit.");
      return;
    }

    hideError();
    feedbackBtn.disabled = true;
    loadingText.textContent = "Evaluating 4-dimension heuristic feedback rubric...";
    loadingState.classList.remove("hidden");

    try {
      const payload = {
        resume_text: resumeText,
        job_description: jdText || null,
        resume_filename: activeFile ? activeFile.name : "resume.pdf",
      };

      const response = await fetch("/api/v1/resumes/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Feedback evaluation failed with HTTP ${response.status}`);
      }

      activeFeedbackResult = data;
      renderFeedbackResult(data);
    } catch (err) {
      showError(err.message || "An error occurred during feedback rubric evaluation.");
    } finally {
      loadingState.classList.add("hidden");
      feedbackBtn.disabled = false;
    }
  });

  // 10. Render Feedback Rubric Result
  function renderFeedbackResult(data) {
    // Total score & tier
    feedbackTotalScore.textContent = data.total_score.toFixed(1);
    feedbackTierBadge.textContent = data.index_label;
    feedbackTierBadge.className = "feedback-tier-badge";
    if (data.index_label === "Exemplary") {
      feedbackTierBadge.classList.add("tier-exemplary");
    } else if (data.index_label === "Proficient") {
      feedbackTierBadge.classList.add("tier-proficient");
    } else if (data.index_label === "Developing") {
      feedbackTierBadge.classList.add("tier-developing");
    } else {
      feedbackTierBadge.classList.add("tier-needs-work");
    }

    // Prioritized Recommendations
    feedbackRecommendationsList.innerHTML = "";
    if (data.prioritized_recommendations && data.prioritized_recommendations.length > 0) {
      data.prioritized_recommendations.forEach((rec) => {
        const li = document.createElement("li");
        li.textContent = rec;
        feedbackRecommendationsList.appendChild(li);
      });
    }

    // Helper to render dimension card
    function renderDimension(cardPrefix, dimData) {
      const scoreElem = document.getElementById(`dim-${cardPrefix}-score`);
      const statusElem = document.getElementById(`dim-${cardPrefix}-status`);
      const summaryElem = document.getElementById(`dim-${cardPrefix}-summary`);
      const evidenceElem = document.getElementById(`dim-${cardPrefix}-evidence`);

      if (!scoreElem || !statusElem || !summaryElem || !evidenceElem) return;

      scoreElem.textContent = `${dimData.score.toFixed(1)} / ${dimData.max_score.toFixed(0)} pts`;
      statusElem.textContent = dimData.status;
      statusElem.className = "dim-status-pill";
      if (dimData.status === "Strong") {
        statusElem.classList.add("status-strong");
      } else if (dimData.status === "Proficient") {
        statusElem.classList.add("status-proficient");
      } else {
        statusElem.classList.add("status-needs-attention");
      }

      summaryElem.textContent = dimData.summary;
      evidenceElem.innerHTML = "";

      // Strengths
      (dimData.strengths || []).forEach((st) => {
        const item = document.createElement("div");
        item.className = "dim-evidence-item item-strength";
        item.textContent = `+ ${st}`;
        evidenceElem.appendChild(item);
      });

      // Deductions
      (dimData.deductions || []).forEach((ded) => {
        const item = document.createElement("div");
        item.className = "dim-evidence-item item-deduction";
        item.textContent = ded;
        evidenceElem.appendChild(item);
      });

      // Suggestions
      (dimData.suggestions || []).forEach((sug) => {
        const item = document.createElement("div");
        item.className = "dim-evidence-item item-suggestion";
        item.textContent = `➜ ${sug}`;
        evidenceElem.appendChild(item);
      });
    }

    renderDimension("structure", data.structure_feedback);
    renderDimension("contact", data.contact_feedback);
    renderDimension("impact", data.impact_feedback);
    renderDimension("skills", data.skills_feedback);

    // Recognized quantified metrics snippets
    metricsSnippetsList.innerHTML = "";
    if (data.quantified_metrics_detected && data.quantified_metrics_detected.length > 0) {
      recognizedMetricsCount.textContent = data.quantified_metrics_detected.length;
      data.quantified_metrics_detected.forEach((qm) => {
        const item = document.createElement("div");
        item.className = "metric-snippet-item";

        const badge = document.createElement("span");
        badge.className = "metric-token-badge";
        badge.textContent = `${qm.metric_type}: ${qm.matched_token}`;
        item.appendChild(badge);

        const snippet = document.createElement("span");
        snippet.className = "metric-snippet-text";
        snippet.textContent = `"${qm.bullet_snippet}"`;
        item.appendChild(snippet);

        metricsSnippetsList.appendChild(item);
      });
      recognizedMetricsSubcard.classList.remove("hidden");
    } else {
      recognizedMetricsSubcard.classList.add("hidden");
    }

    // Detected Canonical Technical Skills in Feedback
    const detectedSkillsSubcard = document.getElementById("feedback-detected-skills-subcard");
    const detectedSkillsCount = document.getElementById("feedback-detected-skills-count");
    const detectedSkillsChips = document.getElementById("feedback-detected-skills-chips");
    if (detectedSkillsSubcard && detectedSkillsCount && detectedSkillsChips) {
      detectedSkillsChips.innerHTML = "";
      if (data.detected_resume_skills && data.detected_resume_skills.length > 0) {
        detectedSkillsCount.textContent = data.detected_resume_skills.length;
        data.detected_resume_skills.forEach((skill) => {
          const chip = document.createElement("span");
          chip.className = "skill-chip";
          chip.textContent = skill;
          detectedSkillsChips.appendChild(chip);
        });
        detectedSkillsSubcard.classList.remove("hidden");
      } else {
        detectedSkillsSubcard.classList.add("hidden");
      }
    }

    feedbackBox.classList.remove("hidden");
  }

  // 11. Clear / Reset Handler (Purges in-memory session)
  function resetSession() {
    activeFile = null;
    activeExtractedText = "";
    activeExtractionResult = null;
    activeStructuredResult = null;
    activeMatchResult = null;
    activeFeedbackResult = null;

    fileInput.value = "";
    dropzoneText.textContent = "Click or drag & drop a PDF or Word (.docx) resume here";
    jobDescriptionInput.value = "";
    extractBtn.disabled = true;
    analyzeStructureBtn.disabled = true;
    feedbackBtn.disabled = true;
    matchBtn.disabled = true;
    clearBtn.classList.add("hidden");
    loadingState.classList.add("hidden");
    hideError();

    // Clear DOM nodes
    extractedTextArea.value = "";
    warningsList.innerHTML = "";
    warningsBox.classList.add("hidden");
    structuredBox.classList.add("hidden");
    matchingResultsCard.classList.add("hidden");
    feedbackBox.classList.add("hidden");
    contactGrid.innerHTML = "";
    sectionPills.innerHTML = "";
    skillsContainer.innerHTML = "";
    feedbackRecommendationsList.innerHTML = "";
    metricsSnippetsList.innerHTML = "";

    const detectedSkillsSubcard = document.getElementById("feedback-detected-skills-subcard");
    const detectedSkillsChips = document.getElementById("feedback-detected-skills-chips");
    if (detectedSkillsSubcard) detectedSkillsSubcard.classList.add("hidden");
    if (detectedSkillsChips) detectedSkillsChips.innerHTML = "";

    // Reset matching card values
    textSimVal.textContent = "--";
    skillOverlapVal.textContent = "--";
    skillOverlapDesc.textContent = "Ratio of recognized JD skills detected on resume.";
    matchedSkillsChips.innerHTML = "";
    missingSkillsChips.innerHTML = "";
    additionalSkillsChips.innerHTML = "";
    matchedCount.textContent = "0";
    missingCount.textContent = "0";
    additionalCount.textContent = "0";

    // Restore placeholder
    resultsContent.classList.add("hidden");
    resultsPlaceholder.classList.remove("hidden");
  }

  clearBtn.addEventListener("click", resetSession);

  // 8. Copy text helper
  copyBtn.addEventListener("click", () => {
    if (extractedTextArea.value) {
      navigator.clipboard.writeText(extractedTextArea.value).then(() => {
        const originalText = copyBtn.textContent;
        copyBtn.textContent = "Copied!";
        setTimeout(() => {
          copyBtn.textContent = originalText;
        }, 1500);
      });
    }
  });

  // Run initial health ping
  checkBackendHealth();
});
