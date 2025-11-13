import { useEffect, useState } from 'react'
import axios from 'axios'
import './App.css'

function App() {
  const [jobTitle, setJobTitle] = useState('')
  const [experience, setExperience] = useState('0-2 years')
  const [location, setLocation] = useState('')
  const [timeFilter, setTimeFilter] = useState('any')
  const [searchId, setSearchId] = useState(null)
  const [status, setStatus] = useState('')
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (!searchId) return

    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`http://127.0.0.1:8000/api/search-jobs/${searchId}`)
        const data = response.data
        setStatus(data.status || '')

        if (data.status === 'COMPLETE') {
          setResults(data.results || null)
          setIsSubmitting(false)
          clearInterval(interval)
        } else if (data.status === 'FAILED') {
          setError(data.message || 'Search failed.')
          setIsSubmitting(false)
          clearInterval(interval)
        }
      } catch (pollError) {
        setError('Error fetching status. Please try again later.')
        setIsSubmitting(false)
        clearInterval(interval)
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [searchId])

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setResults(null)
    setStatus('Searching...')
    setIsSubmitting(true)

    try {
      const payload = {
        job_title: jobTitle,
        experience_level: experience,
        location,
        time_filter: timeFilter,
      }
      const response = await axios.post('http://127.0.0.1:8000/api/search-jobs', payload)
      const data = response.data
      setSearchId(data.search_query_id)
    } catch (submitError) {
      setError('Failed to initiate job search. Please try again.')
      setIsSubmitting(false)
    }
  }

  return (
    <div className="app-container">
      <header>
        <h1>NextRole AI</h1>
        <p>Discover tech job insights with AI-assisted analysis.</p>
      </header>

      <section className="search-form-section">
        <form onSubmit={handleSubmit} className="search-form">
          <div className="form-group">
            <label htmlFor="jobTitle">Job Title</label>
            <input
              id="jobTitle"
              type="text"
              value={jobTitle}
              onChange={(event) => setJobTitle(event.target.value)}
              placeholder="e.g., Software Engineer"
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="experience">Experience</label>
            <select
              id="experience"
              value={experience}
              onChange={(event) => setExperience(event.target.value)}
              disabled={isSubmitting}
            >
              <option value="0-2 years">0-2 years</option>
              <option value="2-5 years">2-5 years</option>
              <option value="5+ years">5+ years</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="location">Location</label>
            <input
              id="location"
              type="text"
              value={location}
              onChange={(event) => setLocation(event.target.value)}
              placeholder="e.g., San Francisco, Remote"
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="timeFilter">Posted Within</label>
            <select
              id="timeFilter"
              value={timeFilter}
              onChange={(event) => setTimeFilter(event.target.value)}
              disabled={isSubmitting}
            >
              <option value="any">Any Time</option>
              <option value="24h">Past 24 hours</option>
              <option value="7d">Past Week</option>
              <option value="30d">Past Month</option>
            </select>
          </div>

          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Searching...' : 'Start Search'}
          </button>
        </form>
      </section>

      <section className="status-section">
        {status && <p className="status-message">Status: {status}</p>}
        {error && <p className="error-message">{error}</p>}
      </section>

      {results && (
        <section className="results-section">
          {results.summaries &&
            results.summaries.length > 0 &&
            ((results.summaries[0]?.top_skills?.length ?? 0) > 0 ||
              (results.summaries[0]?.top_tech_stacks?.length ?? 0) > 0 ||
              results.summaries[0]?.summary_text) && (
              <div className="analysis-panel">
                <h2>Market Analysis</h2>
                {results.summaries[0]?.top_skills?.length > 0 && (
                  <div>
                    <h3>Top Skills</h3>
                    <ul>
                      {results.summaries[0]?.top_skills?.map((skill) => (
                        <li key={skill}>{skill}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {results.summaries[0]?.top_tech_stacks?.length > 0 && (
                  <div>
                    <h3>Top Tech Stacks</h3>
                    <ul>
                      {results.summaries[0]?.top_tech_stacks?.map((tech) => (
                        <li key={tech}>{tech}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {results.summaries[0]?.summary_text && (
                  <div>
                    <h3>Summary</h3>
                    <p>{results.summaries[0]?.summary_text || 'No summary available.'}</p>
                  </div>
                )}
              </div>
            )}

          <div className="jobs-table">
            <h2>Job Listings</h2>
            <table>
              <thead>
                <tr>
                  <th>Job Title</th>
                  <th>Company</th>
                  <th>Location</th>
                  <th>Apply</th>
                </tr>
              </thead>
              <tbody>
                {(results.job_posts || []).map((job) => (
                  <tr key={job._id || `${job.title}-${job.company}`}>
                    <td>{job.title}</td>
                    <td>{job.company}</td>
                    <td>{job.location}</td>
                    <td>
                      {job.apply_url ? (
                        <a href={job.apply_url} target="_blank" rel="noopener noreferrer">
                          Apply
                        </a>
                      ) : (
                        'N/A'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

export default App
