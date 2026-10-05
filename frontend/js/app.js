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
      fetchMatchXAIExplanation(resumeText, jdText);
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

    // Reset XAI matching card
    const matchXaiCard = document.getElementById("match-xai-card");
    if (matchXaiCard) {
      document.getElementById("match-xai-prob-badge").textContent = "Predicting...";
      document.getElementById("match-xai-summary").textContent = "Computing local factor contributions...";
      document.getElementById("match-xai-positive-list").innerHTML = "";
      document.getElementById("match-xai-negative-list").innerHTML = "";
    }

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

  // =========================================================================
  // Explainable AI (XAI) Local Match Explainer (Phase Upgrade)
  // =========================================================================

  async function fetchMatchXAIExplanation(resumeText, jdText) {
    const badge = document.getElementById("match-xai-prob-badge");
    const summary = document.getElementById("match-xai-summary");
    const posList = document.getElementById("match-xai-positive-list");
    const negList = document.getElementById("match-xai-negative-list");

    if (!badge || !summary || !posList || !negList) return;

    badge.className = "xai-prob-badge";
    badge.textContent = "Computing XAI...";
    summary.textContent = "Analyzing decision boundary and feature contributions...";
    posList.innerHTML = "";
    negList.innerHTML = "";

    try {
      const response = await fetch("/api/v1/evaluation/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_text: resumeText,
          job_description: jdText,
          model_id: "logistic_regression",
        }),
      });

      if (!response.ok) {
        throw new Error(`XAI service returned HTTP ${response.status}`);
      }

      const data = await response.json();

      // Render badge
      const isRel = data.prediction_label.toLowerCase().includes("relevant") && !data.prediction_label.toLowerCase().includes("not");
      badge.textContent = `${data.prediction_label} (${(data.prediction_probability * 100).toFixed(1)}%)`;
      badge.className = isRel ? "xai-prob-badge" : "xai-prob-badge xai-prob-not-relevant";

      // Render summary
      summary.innerHTML = data.plain_language_explanation.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

      // Render positive drivers
      if (data.positive_factors && data.positive_factors.length > 0) {
        data.positive_factors.forEach((f) => {
          const li = document.createElement("li");
          li.innerHTML = `<strong>${f.factor_name}:</strong> ${f.description}`;
          posList.appendChild(li);
        });
      } else {
        const li = document.createElement("li");
        li.textContent = "No prominent positive drivers detected for this pair.";
        posList.appendChild(li);
      }

      // Render negative drivers
      if (data.negative_factors && data.negative_factors.length > 0) {
        data.negative_factors.forEach((f) => {
          const li = document.createElement("li");
          li.innerHTML = `<strong>${f.factor_name}:</strong> ${f.description}`;
          negList.appendChild(li);
        });
      } else {
        const li = document.createElement("li");
        li.textContent = "No substantial negative penalty factors detected.";
        negList.appendChild(li);
      }
    } catch (err) {
      badge.textContent = "XAI Unavailable";
      summary.textContent = "Could not generate local explanation: " + (err.message || "Unknown error");
    }
  }

  // =========================================================================
  // Navigation Tabs & View Switching
  // =========================================================================

  const tabAnalyzer = document.getElementById("tab-analyzer");
  const tabEvaluation = document.getElementById("tab-evaluation");
  const analyzerView = document.getElementById("analyzer-view");
  const evaluationView = document.getElementById("evaluation-view");

  let evaluationSummaryLoaded = false;
  let cachedSummaryData = null;

  if (tabAnalyzer && tabEvaluation && analyzerView && evaluationView) {
    tabAnalyzer.addEventListener("click", () => {
      tabAnalyzer.classList.add("active");
      tabEvaluation.classList.remove("active");
      analyzerView.classList.remove("hidden");
      evaluationView.classList.add("hidden");
    });

    tabEvaluation.addEventListener("click", () => {
      tabEvaluation.classList.add("active");
      tabAnalyzer.classList.remove("active");
      evaluationView.classList.remove("hidden");
      analyzerView.classList.add("hidden");

      if (!evaluationSummaryLoaded) {
        loadEvaluationDashboard();
      }
    });
  }

  // =========================================================================
  // ML Evaluation Dashboard Logic
  // =========================================================================

  const modelSelect = document.getElementById("model-select");

  async function loadEvaluationDashboard() {
    try {
      const response = await fetch("/api/v1/evaluation/summary");
      if (!response.ok) {
        throw new Error(`Failed to load evaluation summary (HTTP ${response.status})`);
      }

      const summary = await response.json();
      cachedSummaryData = summary;
      evaluationSummaryLoaded = true;

      // 1. Render comparison table
      renderComparisonTable(summary.comparison_table);

      // 2. Render workflow stepper
      renderWorkflowStepper(summary.workflow_steps);

      // 3. Render cross-model comparative visualization
      renderComparisonBarChart(summary.comparison_table.rows);

      // 4. Render default model
      renderModelEvaluation(summary.default_model);

      // Initialize interactive XAI tester
      initXAITester();
    } catch (err) {
      console.error("Failed to initialize ML Dashboard:", err);
      showError("Unable to load ML evaluation benchmark: " + (err.message || "Check network/server status."));
    }
  }

  if (modelSelect) {
    modelSelect.addEventListener("change", async (e) => {
      const modelId = e.target.value;
      try {
        const response = await fetch(`/api/v1/evaluation/models/${encodeURIComponent(modelId)}`);
        if (!response.ok) {
          throw new Error(`Model not found or unavailable (HTTP ${response.status})`);
        }
        const modelData = await response.json();
        renderModelEvaluation(modelData);
      } catch (err) {
        showError("Failed to load model details: " + err.message);
      }
    });
  }

  function renderModelEvaluation(model) {
    // A. Metric Cards
    const accEl = document.getElementById("eval-accuracy-val");
    const precEl = document.getElementById("eval-precision-val");
    const recEl = document.getElementById("eval-recall-val");
    const f1El = document.getElementById("eval-f1-val");

    if (accEl) accEl.textContent = `${(model.metrics.accuracy * 100).toFixed(1)}%`;
    if (precEl) precEl.textContent = `${(model.metrics.precision * 100).toFixed(1)}%`;
    if (recEl) recEl.textContent = `${(model.metrics.recall * 100).toFixed(1)}%`;
    if (f1El) f1El.textContent = `${(model.metrics.f1_score * 100).toFixed(1)}%`;

    // B. Model Overview Details
    const nameEl = document.getElementById("eval-model-name");
    const typeEl = document.getElementById("eval-model-type");
    const purpEl = document.getElementById("eval-model-purpose");
    const featsEl = document.getElementById("eval-model-features");
    const methEl = document.getElementById("eval-model-method");
    const rankEl = document.getElementById("eval-model-ranking");
    const metaEl = document.getElementById("eval-dataset-meta");

    if (nameEl) nameEl.textContent = model.model_name;
    if (typeEl) typeEl.textContent = model.model_type;
    if (purpEl) purpEl.textContent = model.purpose;
    if (methEl) methEl.textContent = model.evaluation_method;

    if (rankEl) {
      if (model.ranking_metric_value !== null && model.ranking_metric_value !== undefined) {
        rankEl.textContent = `${model.ranking_metric_name}: ${(model.ranking_metric_value * 100).toFixed(1)}%`;
      } else {
        rankEl.textContent = "N/A (Classification Only)";
      }
    }

    if (metaEl) {
      metaEl.textContent = "25 candidate–job pairs across 5 shared job groups (12 Positive / 13 Negative)";
    }

    if (featsEl) {
      featsEl.innerHTML = "";
      model.input_features.forEach((feat) => {
        const pill = document.createElement("span");
        pill.className = "feat-pill";
        pill.textContent = feat;
        featsEl.appendChild(pill);
      });
    }

    // C. 2x2 Confusion Matrix
    const cm = model.confusion_matrix;
    const total = model.metrics.total_samples || 25;

    const tpEl = document.getElementById("cm-tp");
    const tpPct = document.getElementById("cm-tp-pct");
    const fnEl = document.getElementById("cm-fn");
    const fnPct = document.getElementById("cm-fn-pct");
    const fpEl = document.getElementById("cm-fp");
    const fpPct = document.getElementById("cm-fp-pct");
    const tnEl = document.getElementById("cm-tn");
    const tnPct = document.getElementById("cm-tn-pct");
    const cmExp = document.getElementById("cm-explanation");

    if (tpEl) tpEl.textContent = cm.true_positives;
    if (tpPct) tpPct.textContent = `(${((cm.true_positives / total) * 100).toFixed(1)}%)`;
    if (fnEl) fnEl.textContent = cm.false_negatives;
    if (fnPct) fnPct.textContent = `(${((cm.false_negatives / total) * 100).toFixed(1)}%)`;
    if (fpEl) fpEl.textContent = cm.false_positives;
    if (fpPct) fpPct.textContent = `(${((cm.false_positives / total) * 100).toFixed(1)}%)`;
    if (tnEl) tnEl.textContent = cm.true_negatives;
    if (tnPct) tnPct.textContent = `(${((cm.true_negatives / total) * 100).toFixed(1)}%)`;
    if (cmExp) cmExp.textContent = cm.plain_language_explanation;

    // D. Feature Importance Chart
    renderFeatureImportanceChart(model.feature_importance, model.model_type);
  }

  function renderFeatureImportanceChart(features, modelType) {
    const container = document.getElementById("feature-importance-chart");
    const badge = document.getElementById("fi-type-badge");
    if (!container) return;

    container.innerHTML = "";
    if (badge) {
      badge.textContent = modelType.includes("Linear") || modelType.includes("Support Vector")
        ? "Learned Model Coefficients (β)"
        : "Signal Contribution Weights";
    }

    if (!features || features.length === 0) {
      container.innerHTML = "<p class='text-muted'>No feature importance data available for this model.</p>";
      return;
    }

    const maxScore = Math.max(...features.map((f) => f.importance_score), 0.001);

    features.forEach((feat) => {
      const row = document.createElement("div");
      row.className = "fi-row";

      // Label column
      const labelWrap = document.createElement("div");
      labelWrap.className = "fi-label-wrap";

      const name = document.createElement("span");
      name.className = "fi-name";
      name.textContent = feat.display_name;
      name.title = feat.interpretation;

      const dirBadge = document.createElement("span");
      dirBadge.className = `fi-dir-badge dir-${feat.direction}`;
      dirBadge.textContent = feat.direction === "positive" ? "+ Pos" : (feat.direction === "negative" ? "- Neg" : "Neutral");

      labelWrap.appendChild(dirBadge);
      labelWrap.appendChild(name);

      // Track & Fill column
      const track = document.createElement("div");
      track.className = "fi-track";
      track.title = `${feat.display_name}: ${feat.interpretation}`;

      const fill = document.createElement("div");
      fill.className = `fi-fill fill-${feat.direction}`;
      const fillPct = Math.min(100, Math.max(5, (feat.importance_score / maxScore) * 100));
      fill.style.width = `${fillPct}%`;

      track.appendChild(fill);

      // Value column
      const val = document.createElement("div");
      val.className = "fi-val";
      if (feat.raw_coefficient !== null && feat.raw_coefficient !== undefined) {
        val.textContent = `${feat.raw_coefficient > 0 ? "+" : ""}${feat.raw_coefficient.toFixed(4)}`;
      } else {
        val.textContent = feat.importance_score.toFixed(4);
      }

      row.appendChild(labelWrap);
      row.appendChild(track);
      row.appendChild(val);
      container.appendChild(row);
    });
  }

  function renderComparisonTable(tableData) {
    const tbody = document.getElementById("model-comparison-tbody");
    const ruleText = document.getElementById("selection-rule-text");
    if (!tbody) return;

    if (ruleText && tableData.selection_rule) {
      ruleText.innerHTML = `<strong>Selection Rule:</strong> ${tableData.selection_rule}`;
    }

    tbody.innerHTML = "";
    tableData.rows.forEach((row) => {
      const tr = document.createElement("tr");
      if (row.is_best) {
        tr.className = "best-row";
      }

      const rankStr = row.ranking_metric_value !== null && row.ranking_metric_value !== undefined
        ? `${(row.ranking_metric_value * 100).toFixed(1)}%`
        : "N/A";

      tr.innerHTML = `
        <td>
          <strong>${row.model_name}</strong>
          ${row.is_best ? '<span class="best-badge">Best Model</span>' : ''}
        </td>
        <td><span class="feat-pill">${row.model_type}</span></td>
        <td class="metric-num">${(row.accuracy * 100).toFixed(1)}%</td>
        <td class="metric-num">${(row.precision * 100).toFixed(1)}%</td>
        <td class="metric-num">${(row.recall * 100).toFixed(1)}%</td>
        <td class="metric-num">${(row.f1_score * 100).toFixed(1)}%</td>
        <td class="metric-num">${row.samples || 25}</td>
        <td class="metric-num">${rankStr}</td>
        <td><small>${row.evaluation_method}</small></td>
        <td><small>${row.notes}</small></td>
      `;
      tbody.appendChild(tr);
    });
  }

  function renderWorkflowStepper(steps) {
    const container = document.getElementById("workflow-pipeline");
    if (!container || !steps) return;

    container.innerHTML = "";
    steps.forEach((s) => {
      const box = document.createElement("div");
      box.className = "step-box";
      box.innerHTML = `
        <div class="step-num-badge">${s.step_number}</div>
        <div class="step-title">${s.title}</div>
        <div class="step-desc">${s.description}</div>
        <div class="step-comp">${s.component}</div>
      `;
      container.appendChild(box);
    });
  }

  function renderComparisonBarChart(rows) {
    const container = document.getElementById("comparison-bar-chart");
    if (!container || !rows) return;

    container.innerHTML = "";
    rows.forEach((row) => {
      const group = document.createElement("div");
      group.className = "comp-group-row";

      const name = document.createElement("div");
      name.className = "comp-model-name";
      name.innerHTML = `${row.model_name}${row.is_best ? ' <span class="best-badge">Best</span>' : ''}`;

      const tracks = document.createElement("div");
      tracks.className = "multi-bars-track";

      const accWidth = (row.accuracy * 100).toFixed(1);
      const precWidth = (row.precision * 100).toFixed(1);
      const recWidth = (row.recall * 100).toFixed(1);
      const f1Width = (row.f1_score * 100).toFixed(1);

      tracks.innerHTML = `
        <div class="m-bar bar-acc" style="width: ${accWidth}%" title="Accuracy: ${accWidth}%"></div>
        <div class="m-bar bar-prec" style="width: ${precWidth}%" title="Precision: ${precWidth}%"></div>
        <div class="m-bar bar-rec" style="width: ${recWidth}%" title="Recall: ${recWidth}%"></div>
        <div class="m-bar bar-f1" style="width: ${f1Width}%" title="F1-Score: ${f1Width}%"></div>
      `;

      group.appendChild(name);
      group.appendChild(tracks);
      container.appendChild(group);
    });
  }

  // =========================================================================
  // Interactive Local XAI Explainer Tester
  // =========================================================================

  function initXAITester() {
    const btnStrong = document.getElementById("xai-btn-strong");
    const btnPartial = document.getElementById("xai-btn-partial");
    const btnNone = document.getElementById("xai-btn-none");
    const runBtn = document.getElementById("xai-tester-run-btn");
    const resumeTextarea = document.getElementById("xai-tester-resume");
    const jdTextarea = document.getElementById("xai-tester-jd");
    const resultBox = document.getElementById("xai-tester-result");
    const statusSpan = document.getElementById("xai-tester-status");

    if (!runBtn || !resumeTextarea || !jdTextarea || !resultBox) return;

    const SAMPLE_JD = `Junior Backend Developer
We are seeking a Junior Backend Developer proficient in Python and FastAPI to build resilient web APIs.
Requirements:
• Strong proficiency in Python and modern web frameworks (FastAPI or Django).
• Hands-on experience with relational databases, specifically PostgreSQL.
• Practical knowledge of Docker containerization and version control using Git.`;

    const SAMPLE_STRONG = `Alex Morgan
Email: alex.morgan@example.edu | Phone: +1-555-0101 | GitHub: github.com/alexmorgan

Summary
Computer Science student with strong backend software development experience in Python and FastAPI.

Experience
Software Engineering Intern - CloudCraft Systems (Summer 2024)
• Engineered REST API microservices using Python and FastAPI, handling 1,500 requests per minute.
• Optimized PostgreSQL queries and database schemas, reducing latency by 28%.
• Containerized application services using Docker and automated CI/CD workflows with Git.`;

    const SAMPLE_PARTIAL = `Ryan Cooper
Email: ryan.c@example.edu | Phone: +1-555-0117

Education
B.S. in Computer Science - State University (Expected May 2025)
Relevant Coursework: Web Programming, Data Structures, Relational Databases

Academic Projects
Campus Market Portal
• Built full-stack web application using React, Python, and SQLite.
• Implemented user login and item posting features.`;

    const SAMPLE_NONE = `Jordan Hayes
Email: jordan.h@example.edu | Phone: +1-555-0199

Summary
Hospitality and guest services associate with 3 years of customer-facing experience in boutique hotel reception and banquet operations.

Experience
Guest Experience Specialist - Grand Horizon Hotel (2022 - Present)
• Coordinated guest check-ins, VIP room reservations, and front-desk inquiries.
• Managed catering inventory and organized private dining receptions.`;

    if (btnStrong) {
      btnStrong.addEventListener("click", () => {
        resumeTextarea.value = SAMPLE_STRONG;
        jdTextarea.value = SAMPLE_JD;
      });
    }

    if (btnPartial) {
      btnPartial.addEventListener("click", () => {
        resumeTextarea.value = SAMPLE_PARTIAL;
        jdTextarea.value = SAMPLE_JD;
      });
    }

    if (btnNone) {
      btnNone.addEventListener("click", () => {
        resumeTextarea.value = SAMPLE_NONE;
        jdTextarea.value = SAMPLE_JD;
      });
    }

    runBtn.addEventListener("click", async () => {
      const resVal = resumeTextarea.value.trim();
      const jdVal = jdTextarea.value.trim();

      if (!resVal || !jdVal) {
        alert("Please provide both a candidate resume and a target job description to run XAI explanation.");
        return;
      }

      runBtn.disabled = true;
      if (statusSpan) statusSpan.textContent = "Computing feature log-odds decomposition...";

      try {
        const response = await fetch("/api/v1/evaluation/explain", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            resume_text: resVal,
            job_description: jdVal,
            model_id: "logistic_regression",
          }),
        });

        if (!response.ok) {
          throw new Error(`Explanation failed with HTTP ${response.status}`);
        }

        const data = await response.json();

        // Render Tester Result Box
        const badge = document.getElementById("xai-res-badge");
        const prob = document.getElementById("xai-res-prob");
        const score = document.getElementById("xai-res-score");
        const modelTag = document.getElementById("xai-res-model");
        const summary = document.getElementById("xai-res-summary");
        const posList = document.getElementById("xai-res-pos-list");
        const negList = document.getElementById("xai-res-neg-list");
        const fiTbody = document.getElementById("xai-res-fi-tbody");

        const isRel = data.prediction_label.toLowerCase().includes("relevant") && !data.prediction_label.toLowerCase().includes("not");

        if (badge) {
          badge.textContent = data.prediction_label;
          badge.className = isRel ? "xai-pred-badge badge-rel" : "xai-pred-badge badge-not-rel";
        }

        if (prob) prob.textContent = `Estimated Probability: ${(data.prediction_probability * 100).toFixed(1)}%`;
        if (score) score.textContent = `Decision Log-Odds: ${data.decision_score > 0 ? "+" : ""}${data.decision_score.toFixed(2)}`;
        if (modelTag) modelTag.textContent = data.model_name;
        if (summary) summary.innerHTML = data.plain_language_explanation.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

        // Positive drivers
        if (posList) {
          posList.innerHTML = "";
          if (data.positive_factors && data.positive_factors.length > 0) {
            data.positive_factors.forEach((f) => {
              const li = document.createElement("li");
              li.innerHTML = `<strong>${f.factor_name}:</strong> ${f.description}`;
              posList.appendChild(li);
            });
          } else {
            const li = document.createElement("li");
            li.textContent = "No prominent positive alignment drivers.";
            posList.appendChild(li);
          }
        }

        // Negative drivers
        if (negList) {
          negList.innerHTML = "";
          if (data.negative_factors && data.negative_factors.length > 0) {
            data.negative_factors.forEach((f) => {
              const li = document.createElement("li");
              li.innerHTML = `<strong>${f.factor_name}:</strong> ${f.description}`;
              negList.appendChild(li);
            });
          } else {
            const li = document.createElement("li");
            li.textContent = "No limiting factor penalties detected.";
            negList.appendChild(li);
          }
        }

        // Feature table
        if (fiTbody) {
          fiTbody.innerHTML = "";
          data.feature_contributions.forEach((f) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
              <td><strong>${f.display_name}</strong></td>
              <td><span class="fi-dir-badge dir-${f.direction}">${f.direction === "positive" ? "+ Pos" : (f.direction === "negative" ? "- Neg" : "Neutral")}</span></td>
              <td class="metric-num">${f.raw_coefficient > 0 ? "+" : ""}${f.raw_coefficient.toFixed(4)}</td>
              <td><small>${f.interpretation}</small></td>
            `;
            fiTbody.appendChild(tr);
          });
        }

        resultBox.classList.remove("hidden");
        if (statusSpan) statusSpan.textContent = "Explanation complete.";
      } catch (err) {
        if (statusSpan) statusSpan.textContent = "Error: " + err.message;
      } finally {
        runBtn.disabled = false;
      }
    });
  }

  // Run initial health ping
  checkBackendHealth();
});

