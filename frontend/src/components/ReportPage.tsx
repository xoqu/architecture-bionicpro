import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface ReportRow {
  user_id: string;
  report_date: string;
  prosthesis_id: string;
  customer_name: string;
  city: string;
  events_count: number;
  avg_response_ms: number;
  max_response_ms: number;
  avg_battery: number;
  grip_count: number;
  open_count: number;
  pinch_count: number;
}

interface ReportResponse {
  user_id: string;
  date_from: string;
  date_to: string;
  processed_until: string | null;
  partial: boolean;
  message: string | null;
  rows: ReportRow[];
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      try {
        await keycloak.updateToken(30);
      } catch {
        setError('Session expired');
        return;
      }

      const params = new URLSearchParams();
      if (dateFrom) {
        params.set('date_from', dateFrom);
      }
      if (dateTo) {
        params.set('date_to', dateTo);
      }
      const query = params.toString();
      const response = await fetch(
        `${process.env.REACT_APP_API_URL}/reports${query ? `?${query}` : ''}`,
        {
          headers: {
            Authorization: `Bearer ${keycloak.token}`,
          },
        }
      );

      if (!response.ok) {
        let detail = `Request failed: ${response.status}`;
        try {
          const body: { detail?: string } = await response.json();
          if (body.detail) {
            detail = body.detail;
          }
        } catch {
          // Тело ошибки может быть пустым.
        }
        setReport(null);
        setError(detail);
        return;
      }

      const body: ReportResponse = await response.json();
      setReport(body);

      const blob = new Blob([JSON.stringify(body, null, 2)], {
        type: 'application/json',
      });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `report-${body.user_id}.json`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!initialized) {
    return <div>Loading...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={() => keycloak.login()}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
      </div>
    );
  }

  const username =
    typeof keycloak.tokenParsed?.preferred_username === 'string'
      ? keycloak.tokenParsed.preferred_username
      : '';

  return (
    <div className="flex flex-col items-center min-h-screen bg-gray-100 py-10 px-4">
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-5xl">
        <h1 className="text-2xl font-bold mb-2">Usage Reports</h1>
        <p className="text-sm text-gray-600 mb-6">Signed in as {username}</p>

        <div className="flex flex-wrap gap-4 mb-6">
          <label className="text-sm text-gray-700">
            From
            <input
              type="date"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
              className="mt-1 block border border-gray-300 rounded px-2 py-1"
            />
          </label>
          <label className="text-sm text-gray-700">
            To
            <input
              type="date"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
              className="mt-1 block border border-gray-300 rounded px-2 py-1"
            />
          </label>
        </div>

        <button
          onClick={downloadReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Generating Report...' : 'Download Report'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">{error}</div>
        )}

        {report?.message && (
          <div className="mt-4 p-4 bg-amber-100 text-amber-800 rounded">
            {report.message}
          </div>
        )}

        {report && (
          <div className="mt-6 overflow-x-auto">
            <p className="text-sm text-gray-600 mb-3">
              {report.user_id}: {report.date_from} — {report.date_to}
              {report.processed_until
                ? `, processed until ${report.processed_until}`
                : ''}
            </p>
            {report.rows.length === 0 ? (
              <p className="text-gray-600">No rows for this period.</p>
            ) : (
              <table className="min-w-full text-sm text-left border-collapse">
                <thead>
                  <tr className="border-b border-gray-200 text-gray-500">
                    <th className="py-2 pr-4">Date</th>
                    <th className="py-2 pr-4">Customer</th>
                    <th className="py-2 pr-4">City</th>
                    <th className="py-2 pr-4">Prosthesis</th>
                    <th className="py-2 pr-4">Events</th>
                    <th className="py-2 pr-4">Avg response, ms</th>
                    <th className="py-2 pr-4">Battery</th>
                    <th className="py-2 pr-4">Grip / Open / Pinch</th>
                  </tr>
                </thead>
                <tbody>
                  {report.rows.map((row) => (
                    <tr key={row.report_date} className="border-b border-gray-100">
                      <td className="py-2 pr-4">{row.report_date}</td>
                      <td className="py-2 pr-4">{row.customer_name}</td>
                      <td className="py-2 pr-4">{row.city}</td>
                      <td className="py-2 pr-4">{row.prosthesis_id}</td>
                      <td className="py-2 pr-4">{row.events_count}</td>
                      <td className="py-2 pr-4">{row.avg_response_ms}</td>
                      <td className="py-2 pr-4">{row.avg_battery}</td>
                      <td className="py-2 pr-4">
                        {row.grip_count} / {row.open_count} / {row.pinch_count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
