# Project Roadmap & TODOs

## Phase 1: MVP (Current - In Progress)

### Core Infrastructure ✅
- [x] FastAPI application structure
- [x] Reolink NVR connection via reolink_aio
- [x] Home Assistant add-on manifest and Docker setup
- [x] API endpoint structure
- [x] Health check and device info endpoints
- [x] Documentation (README, INSTALL, DEVELOPMENT)

### Core Recording Search 🔄 (Next Priority)
- [ ] Implement `Host.search_recordings()` or equivalent using reolink_aio
- [ ] Parse Reolink API response for recording metadata
- [ ] Filter recordings by event type (DOORBELL, PERSON, MOTION, ANIMAL)
- [ ] Return structured JSON with clip metadata
- [ ] Handle timezone conversions
- [ ] Add pagination support for large result sets

### Basic API Endpoints ⏳ (After search)
- [ ] GET `/api/search` - working with actual data
- [ ] GET `/api/download/{clip_id}` - clip download
- [ ] GET `/api/snapshot/{clip_id}` - snapshot extraction

## Phase 2: Enhanced Features

### Advanced Recording Management
- [ ] VOD (Video on Demand) streaming URLs
- [ ] Multi-channel search simultaneously
- [ ] Event type filtering improvements
- [ ] Recording metadata caching

### Stream URL Generation
- [ ] RTSP URLs for live streaming
- [ ] RTMP URLs for external streaming
- [ ] FLV URLs for web browser playback
- [ ] Main vs sub-stream selection

### Dashboard Cards
- [ ] Custom Lovelace card for clip display
- [ ] Thumbnail generation from clips
- [ ] Video player integration
- [ ] Event timeline visualization

## Phase 3: Real-time Features

### Event Webhooks
- [ ] Subscribe to Reolink real-time events
- [ ] Forward events to Home Assistant webhooks
- [ ] Event type filtering at subscription level
- [ ] Persistent webhook registry

### Smart Notifications
- [ ] Automatic clip generation on events
- [ ] AI-powered event context in notifications
- [ ] Quick actions in notifications (unlock, dismiss)

## Phase 4: Advanced Integration

### Automation Helpers
- [ ] Pre-built automation templates
- [ ] Event-based triggers for HA
- [ ] Clip archival and retention policies

### Analytics
- [ ] Event statistics and trends
- [ ] Visitor analytics
- [ ] Peak time analysis

## Implementation Details

### Recording Search Algorithm

1. **Identify recording search API in reolink_aio**
   - Check `Host` class methods
   - Look for `search_recordings()` or `search_rec()`
   - Review source code if needed

2. **Query by date range**
   - Convert YYYY-MM-DD to NVR timestamp format
   - Handle timezone considerations
   - Implement date range splitting for large ranges

3. **Filter by event type**
   - Parse recording metadata for event type field
   - Map: DOORBELL → Visitor, PERSON → Person Detection, etc.
   - Handle cases where event type isn't available

4. **Return structured data**
   - Timestamp (ISO 8601)
   - Duration in seconds
   - Event type
   - File name / ID
   - Stream URL (RTSP/FLV)
   - Thumbnail URL (generated or extracted)

### Reolink API Notes

From network analysis and reolink_aio:
- Authentication uses token-based sessions
- Recordings are stored in proprietary format
- Event metadata may be limited in API response
- Sub-streams have lower resolution but faster access

### Testing Strategy

1. **Unit tests**
   - API endpoint logic
   - Date/time parsing and validation
   - Filter logic for event types

2. **Integration tests**
   - Real NVR connection (use test NVR or mock)
   - Search with various date ranges
   - Filter by different event types

3. **Manual testing**
   - Test with actual Reolink NVR
   - Verify clips play correctly
   - Test notification integration

## Known Challenges

### 1. Recording Search API Availability
**Challenge:** reolink_aio may not expose recording search directly
**Solution:** 
- Inspect reolink_aio source for API methods
- If not available, use HTTP client to call raw API
- Reference community documentation for search parameters

### 2. Event Type Detection
**Challenge:** Event metadata may not be explicitly stored
**Solution:**
- Determine event type from file naming or metadata
- Fall back to time-based correlation with binary sensor events
- Store event type mapping in database

### 3. Timezone Handling
**Challenge:** NVR and Home Assistant may be in different timezones
**Solution:**
- Store all times in UTC internally
- Convert to user's timezone in response
- Document timezone expectations in API docs

### 4. Performance with Large Result Sets
**Challenge:** Days with many recordings could be slow
**Solution:**
- Implement pagination in search results
- Add limit/offset parameters
- Cache frequently accessed dates

## Success Criteria

Phase 1 is complete when:
- ✅ API can search NVR recordings by date/time
- ✅ Filtering by event type works reliably
- ✅ Clips can be streamed or downloaded
- ✅ Integration with Home Assistant notifications works
- ✅ Documentation is clear and complete
- ✅ Add-on installs and runs on HA Green

## Development Timeline Estimate

- **Week 1:** Recording search implementation
- **Week 2:** Download/stream endpoint
- **Week 3:** Testing and bug fixes
- **Week 4:** Documentation polish and Phase 2 planning

## Contributing

If you want to contribute:
1. Pick a TODO item
2. Create a feature branch
3. Implement with tests
4. Submit a pull request
5. Update documentation

See [DEVELOPMENT.md](DEVELOPMENT.md) for setup instructions.

## Questions & Notes

- **Q: Why not use media_source directly?**
  - A: media_source has limitations with event filtering. This bypasses those limitations.

- **Q: Can this work with other NVRs?**
  - A: Not in current form, but framework could be extended for other Reolink models or brands.

- **Q: What about privacy?**
  - A: All communication is local (LAN). No data is sent to Reolink cloud or third parties.
