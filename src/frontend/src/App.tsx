import { lazy, Suspense } from 'react'
import { AppHeader } from '@/components/app-header'
import { Toaster } from '@/components/ui/sonner'
import { HomePage } from '@/features/home/home-page'
import { useRoute } from '@/lib/use-route'

// The other pages are loaded when first opened, which keeps the landing page light.
const FindPage = lazy(() => import('@/features/find/find-page').then((m) => ({ default: m.FindPage })))
const ReferencePage = lazy(() => import('@/features/reference/reference-page').then((m) => ({ default: m.ReferencePage })))

export default function App() {
  const { route, param, navigate } = useRoute()
  return (
    <>
      <AppHeader route={route} onNavigate={navigate} />
      {route === 'home' && <HomePage onNavigate={navigate} />}
      <Suspense fallback={null}>
        {route === 'find' && <FindPage id={param} onNavigate={navigate} />}
        {route === 'reference' && <ReferencePage />}
      </Suspense>
      <Toaster />
    </>
  )
}
