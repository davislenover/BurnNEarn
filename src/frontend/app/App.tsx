import { StatusBar } from 'expo-status-bar';
import DemoScreen from './screens/dashboard/DemoScreen';

// Root component: the app opens directly on the demo screen.
export default function App() {
  return (
    <>
      <DemoScreen />
      {/* Phone top bar (time, battery) */}
      <StatusBar style="auto" />
    </>
  );
}
