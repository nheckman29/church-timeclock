import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter, Route, Routes } from "react-router"
import "./index.css"

import AdminLayout from './components/AdminLayout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import EmployeeDetail from './pages/EmployeeDetail.jsx'
import Employees from './pages/Employees.jsx'
import ExportCheck from './pages/ExportCheck.jsx'
import Kiosk from './pages/Kiosk.jsx'
import Login from './pages/Login.jsx'
import Settings from './pages/Settings.jsx'
import TimeCard from './pages/TimeCard.jsx'

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Kiosk />} />
        <Route path="/time-card" element={<TimeCard />} />
        <Route path="/admin/login" element={<Login />} />
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="employees" element={<Employees />} />
          <Route path="employees/:id" element={<EmployeeDetail />} />
          <Route path="export" element={<ExportCheck />} />
          <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Kiosk />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
