const express = require("express");
const cors = require("cors");
const dotenv = require("dotenv");
const axios = require("axios");

dotenv.config();

const app = express();

app.use(cors());
app.use(express.json());

const PORT = process.env.PORT || 5000;

app.get("/", (req, res) => {
  res.json({
    message: "ScamTrace API Gateway Running",
    project: "J26-SE-316"
  });
});

app.post("/api/analyze", async (req, res) => {
  try {
    const { url, socialText, repoUrl } = req.body;

    const results = {
      c1_url_domain: null,
      c2_html_content: null,
      c3_social_visual: null,
      c4_code_audit: null
    };

    try {
      const c1 = await axios.post(`${process.env.C1_URL}/analyze-url`, { url });
      results.c1_url_domain = c1.data;
    } catch {
      results.c1_url_domain = {
        component: "C1_URL_DOMAIN",
        status: "service_not_connected",
        score: 0
      };
    }

    try {
      const c2 = await axios.post(`${process.env.C2_URL}/analyze-html`, { url });
      results.c2_html_content = c2.data;
    } catch {
      results.c2_html_content = {
        component: "C2_HTML_CONTENT",
        status: "service_not_connected",
        score: 0
      };
    }

    try {
      const c3 = await axios.post(`${process.env.C3_URL}/analyze-visual`, {
        url,
        socialText
      });
      results.c3_social_visual = c3.data;
    } catch {
      results.c3_social_visual = {
        component: "C3_SOCIAL_VISUAL",
        status: "service_not_connected",
        score: 0
      };
    }

    try {
      const c4 = await axios.post(`${process.env.C4_URL}/analyze-code`, { repoUrl });
      results.c4_code_audit = c4.data;
    } catch {
      results.c4_code_audit = {
        component: "C4_CODE_AUDIT",
        status: "service_not_connected",
        score: 0
      };
    }

    const scores = Object.values(results).map(item => item.score || 0);
    const overallScore = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);

    let finalLabel = "Low Risk";
    if (overallScore >= 75) finalLabel = "High Risk Scam";
    else if (overallScore >= 50) finalLabel = "Medium Risk";
    else if (overallScore >= 25) finalLabel = "Suspicious";

    res.json({
      analysis_id: `SCAM-${Date.now()}`,
      input: {
        url,
        socialText,
        repoUrl
      },
      overall_score: overallScore,
      final_label: finalLabel,
      component_results: results
    });

  } catch (error) {
    res.status(500).json({
      message: "Analysis failed",
      error: error.message
    });
  }
});

app.listen(PORT, () => {
  console.log(`ScamTrace API Gateway running on port ${PORT}`);
});
