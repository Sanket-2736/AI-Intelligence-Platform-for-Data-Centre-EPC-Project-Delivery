# Operations Checklist

For operations teams managing EPC Intelligence Platform in production.

---

## 🎯 Quick Reference

### Emergency Contacts
- **Tech Lead**: [Name] - [Email] - [Phone]
- **DevOps**: [Name] - [Email] - [Phone]
- **On-Call Rotation**: See wiki

### Critical URLs
- **Production Frontend**: https://epc-intelligence.vercel.app
- **Production API**: https://epc-intelligence-api.onrender.com
- **API Docs**: https://epc-intelligence-api.onrender.com/docs
- **Render Dashboard**: https://dashboard.render.com
- **Vercel Dashboard**: https://vercel.com
- **Supabase Console**: https://app.supabase.com

---

## 📅 Daily Operations

### Morning Check (15 minutes)

**Every morning before business hours:**

```bash
# 1. Verify services are up
curl -s https://epc-intelligence-api.onrender.com/health | jq .

# 2. Check status page
# Go to https://status.onrender.com (if applicable)

# 3. Review overnight logs
# Render Dashboard → Logs → Review ERROR entries

# 4. Verify no critical alerts
# Monitoring dashboard → Check alert queue
```

**Expected output:**
```json
{
  "status": "healthy",
  "services": {
    "supabase": {"status": "connected"},
    "chromadb": {"status": "ready"},
    "cerebras": {"status": "ready"}
  }
}
```

### End of Day Check (10 minutes)

**Every evening before shift ends:**

```bash
# 1. Check error rate
# Render Dashboard → Metrics → Error Rate
# Should be < 0.1% (one error per 1000 requests)

# 2. Check response time
# Metrics → Average Response Time
# Should be < 1 second for API calls

# 3. Review critical logs
# Logs → Filter by ERROR level
# Investigate any new error patterns

# 4. Document any incidents
# Incident log → Add entry if applicable
```

---

## 🚨 Incident Response

### Alert: API Response Time > 3 seconds

**Step 1: Verify Issue (2 min)**
```bash
curl -w "@measure.txt" https://epc-intelligence-api.onrender.com/health
# time_namelookup, time_connect, time_appconnect, time_pretransfer, time_redirect, time_starttransfer, time_total
```

**Step 2: Check Cerebras Usage (2 min)**
```bash
curl https://epc-intelligence-api.onrender.com/health | jq '.services.cerebras.usage'
# Check avg_response_time_ms
# If > 1500ms, likely Cerebras latency, not our issue
```

**Step 3: Check Backend Logs (2 min)**
- Render Dashboard → Select epc-intelligence-api → Logs
- Filter for ERROR or WARN entries in last hour
- Look for pattern in slow requests

**Step 4: Scale if Needed (5 min)**
- Render Dashboard → Instance Type
- Consider upgrading from Free to Starter or Standard
- Click "Update" to apply (no downtime)

**Step 5: Escalate if Unresolved (5 min)**
- Contact Tech Lead if issue persists > 15 minutes
- Prepare: Error screenshots, log excerpts, timeline

---

### Alert: Error Rate > 1%

**Step 1: Identify Error Pattern (3 min)**
```bash
# Render Dashboard → Logs → Filter by ERROR
# Look for:
# - Repeated error message (indicates pattern)
# - Specific endpoint causing errors
# - Recent deployments that triggered errors
```

**Step 2: Check Recent Deployments (2 min)**
- Render Dashboard → Deployments
- Did new code deploy in last 30 minutes?
- Note: redeploy timestamp

**Step 3: Gather Information (5 min)**
- Screenshot of error logs (first 10 errors)
- Note time window (when did errors start)
- Identify if specific agent is affected
- Check if error is intermittent or consistent

**Step 4: Rollback if Critical (5 min)**
**If causing 10%+ error rate:**
- Render Dashboard → Deployments
- Find last known good deployment
- Click "Redeploy"
- Wait for health check to pass

**If not critical:**
- Don't rollback immediately
- Escalate to Tech Lead
- Monitor closely

---

### Alert: Service Unavailable (503)

**Step 1: Immediate Actions (2 min)**
```bash
# 1. Check if Render is down
curl https://status.render.com

# 2. Check health endpoint
curl https://epc-intelligence-api.onrender.com/health

# 3. Check Supabase status
# Go to https://status.supabase.com
```

**Step 2: Check Logs (3 min)**
- Render Dashboard → epc-intelligence-api → Logs
- Look for service initialization errors
- Check for database connection errors

**Step 3: Restart Service (2 min)**
- Render Dashboard → Select service
- Click "Restart" button
- Wait for health check to pass

**Step 4: Verify Recovery (2 min)**
```bash
curl https://epc-intelligence-api.onrender.com/health
# Should return 200 status
```

**Step 5: Escalate if Not Recovered (5 min)**
- Contact Tech Lead immediately
- Provide: restart time, logs, health check response
- Be ready for manual diagnostics

---

## 📊 Weekly Operations Review

**Every Friday afternoon:**

### 1. Performance Review (15 minutes)

```bash
# Get weekly statistics
curl https://epc-intelligence-api.onrender.com/health | jq '.services.cerebras.usage'

# Chart from dashboard:
# - Uptime percentage (target: >99.5%)
# - Average response time (target: <1s)
# - Error rate (target: <0.1%)
# - Request volume
```

### 2. Cost Review (10 minutes)

- Render Dashboard → Usage & Billing
  - Check current month spend
  - Verify no unexpected charges
  - Note: Free tier = $0, Starter = $7/month

- Vercel Dashboard → Usage & Billing
  - Check bandwidth usage
  - Verify no unexpected charges
  - Note: Free tier has bandwidth limits

- Supabase Dashboard → Billing
  - Check database usage
  - Verify storage under free tier (500MB)
  - Note: Can upgrade if needed

### 3. Dependency Review (15 minutes)

```bash
# Check for outdated packages (backend)
cd backend
pip list --outdated

# Check for outdated packages (frontend)
cd ../frontend
npm outdated
```

**Action**: If critical security updates available, escalate to DevOps

### 4. Log Review (15 minutes)

- Render Dashboard → Logs → Last 7 days
- Filter by WARN or ERROR
- Document any recurring patterns
- File incident report if needed

### 5. Capacity Planning (10 minutes)

- Review weekly traffic trends
- If consistently near limits, plan upgrade
- Current limits:
  - Cerebras: 100 requests/day free tier
  - Supabase: 500MB database free tier
  - Vercel: 100GB bandwidth free tier

---

## 🔄 Monthly Maintenance

**Every month on the 1st:**

### 1. Database Backup Verification (20 minutes)

```bash
# Supabase Dashboard → Backups
# Verify:
# - Last backup completed successfully (should be yesterday)
# - Backup size is reasonable (10-100MB)
# - No backup errors in log
```

**Action**: If backup failed, contact Supabase support

### 2. Dependency Updates (30 minutes)

**Backend:**
```bash
cd backend
pip install --upgrade pip
pip install --upgrade -r requirements.txt
pip freeze > requirements_new.txt
# Review changes in requirements_new.txt
# Test in staging environment
# If good, commit and deploy
```

**Frontend:**
```bash
cd frontend
npm update
npm audit fix
npm run build  # Ensure no build errors
# Review changes in package-lock.json
# Test in staging environment
# If good, commit and deploy
```

### 3. Security Review (30 minutes)

```bash
# Backend security scan
cd backend
pip audit  # Check for known vulnerabilities

# Frontend security scan
cd ../frontend
npm audit  # Check for known vulnerabilities
```

**Action**: Fix any high/critical vulnerabilities immediately

### 4. Documentation Update (15 minutes)

- Review if any documentation is outdated
- Check if new runbooks needed
- Update version numbers if deployed new release
- Note any operational improvements learned

---

## 🔐 Security Operations

### Weekly Security Check (15 minutes)

- [ ] Review recent deployments for unexpected changes
- [ ] Check that all secrets are in environment variables (not in code)
- [ ] Verify CORS is restricted to known domains
- [ ] Check that DEBUG is set to false in production

### Monthly Security Audit (30 minutes)

- [ ] Verify API keys are rotated (every 90 days)
- [ ] Check Supabase Row Level Security (RLS) is enabled
- [ ] Review recent logins to Render/Vercel dashboards
- [ ] Verify no CI/CD secrets exposed in logs

---

## 📈 Monitoring & Alerting

### Recommended Monitoring Setup

**Render Built-in:**
- ✅ Health check (every 30s)
- ✅ Memory usage
- ✅ CPU usage
- ✅ Request count
- ✅ Error count

**Vercel Built-in:**
- ✅ Build success/failure
- ✅ Deployment status
- ✅ Analytics (traffic, performance)

**Optional Add-ons:**
- **Sentry** - Error tracking and alerting
- **DataDog** - Full APM and monitoring
- **PagerDuty** - On-call and incident management

### Alert Configuration

**Critical Alerts (immediate escalation):**
- Service down (503)
- Error rate > 5%
- Database connection error

**Warning Alerts (review and action):**
- Response time > 3s
- Error rate > 1%
- High CPU (>80%)
- High memory (>80%)

---

## 📞 Escalation Path

### Severity 1 (Critical - Page immediately)
- Production service completely down
- Data loss or corruption
- Security breach
- All users affected

**Action**: Page on-call engineer immediately

### Severity 2 (High - Urgent action needed)
- Degraded performance (>50% users affected)
- Major feature broken
- Database partially unavailable

**Action**: Contact Tech Lead, begin investigation

### Severity 3 (Medium - Action within 4 hours)
- Single feature broken
- Performance degradation
- One agent not responding

**Action**: Escalate to Dev team, plan fix

### Severity 4 (Low - Schedule fix)
- Minor UI issue
- Documentation error
- Performance optimization

**Action**: Add to backlog, schedule for next sprint

---

## 📋 Runbooks

### Runbook: Increase API Performance

1. Check current response time
   ```bash
   curl https://epc-intelligence-api.onrender.com/health
   # Check avg_response_time_ms
   ```

2. Possible issues & solutions:
   - **Cerebras slow (>1500ms)**: LLM inference time, normal
   - **DB slow (<100ms)**: ChromaDB or Supabase latency
   - **API overhead (>500ms)**: Consider upgrade

3. Performance upgrade path:
   - Current: Free tier (0.5 CPU, 0.5 GB RAM)
   - Upgrade: Starter ($7/month, 1 CPU, 0.5 GB RAM)
   - Further: Standard ($12/month, 2 CPU, 1 GB RAM)

4. To upgrade:
   - Render Dashboard → Select service
   - Click "Settings" → "Plan"
   - Select new plan → Click "Upgrade"
   - No downtime required

---

### Runbook: Restore from Backup

1. Check backup status:
   - Supabase Dashboard → Backups
   - Note backup timestamp

2. Restore database:
   - Supabase Dashboard → Backups
   - Click restore point → Confirm
   - Wait for restore to complete (~5 min)

3. Verify restoration:
   ```bash
   curl https://epc-intelligence-api.onrender.com/health
   # Should return healthy status
   ```

4. Alert stakeholders of data restore

---

### Runbook: Deploy Hotfix

1. Code review and merge hotfix to main branch

2. Automatic deployment:
   - Render auto-deploys on git push to main
   - Vercel auto-deploys on git push to main
   - Monitor health endpoint during deploy

3. Verify deployment:
   ```bash
   curl https://epc-intelligence-api.onrender.com/health
   ```

4. Post-deployment validation:
   - Test critical agent workflow
   - Check error logs for new errors
   - Verify response times normal

---

## 🎓 Training

### For New Operators (Day 1)

1. **Morning (2 hours)**
   - Read QUICKSTART.md
   - Read README.md
   - Run smoke tests locally

2. **Afternoon (2 hours)**
   - Walk through DEPLOYMENT.md
   - Set up local dev environment
   - Run demo walkthrough

3. **Day 2**
   - Shadow current operator for morning check
   - Shadow incident response
   - Learn dashboard navigation

### For On-Call Rotation (Monthly)

- Review all runbooks
- Practice incident response scenarios
- Update escalation contacts
- Verify access to all dashboards

---

## 📝 Incident Template

**Use when filing incident report:**

```
Title: [Brief description]
Severity: [1-4]
Start Time: [ISO 8601]
Duration: [minutes]
Impact: [number of users / percentage]

Root Cause:
[What caused the incident]

Timeline:
[When was issue detected]
[When was escalation decided]
[When was fix applied]
[When was service recovered]

Resolution:
[What was done to fix]
[Any rollbacks or manual intervention]

Prevention:
[What can we do to prevent recurrence]

Lessons Learned:
[What did we learn from this incident]
```

---

## 🔧 Useful Commands

### Health Check
```bash
curl https://epc-intelligence-api.onrender.com/health | jq .
```

### API Documentation
```
https://epc-intelligence-api.onrender.com/docs
```

### View Logs (via curl)
```bash
# Requires auth token (Render API)
curl -H "Authorization: Bearer $RENDER_API_TOKEN" \
  https://api.render.com/v1/services/epc-api/events
```

### Check DNS
```bash
nslookup epc-intelligence-api.onrender.com
```

### Measure Response Time
```bash
time curl https://epc-intelligence-api.onrender.com/health
```

### Test API Endpoint
```bash
curl -X GET \
  "https://epc-intelligence-api.onrender.com/api/dashboard/summary" \
  -H "Content-Type: application/json"
```

---

## 📞 Support Contacts

**For Render Issues:**
- Support: support@render.com
- Docs: https://render.com/docs
- Status: https://status.render.com

**For Vercel Issues:**
- Support: support@vercel.com
- Docs: https://vercel.com/docs
- Status: https://www.vercel-status.com

**For Supabase Issues:**
- Support: Support portal in dashboard
- Docs: https://supabase.com/docs
- Status: https://status.supabase.com

**For Cerebras Issues:**
- Support: api@cerebras.net
- Docs: https://www.cerebras.net/api-docs

---

## ✅ Operations Sign-Off

By implementing this operations checklist, the platform has:

- ✅ Daily health monitoring
- ✅ Incident response procedures
- ✅ Weekly maintenance reviews
- ✅ Monthly security audits
- ✅ Clear escalation paths
- ✅ Documented runbooks
- ✅ Training procedures
- ✅ SLA targets (>99.5% uptime, <0.1% error rate)

---

**Document Version**: 1.0.0  
**Last Updated**: 2026-06-22  
**Next Review**: 2026-07-22  
**Owner**: Operations Team
