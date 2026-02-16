import { Rocket } from "lucide-react";

export default function JobSeekerHome() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="max-w-md text-center">
        <Rocket className="mx-auto mb-6 h-16 w-16 text-blue-500" />
        <h1 className="mb-3 text-2xl font-bold text-gray-900">
          Coming Soon
        </h1>
        <p className="text-gray-500">
          We're building an amazing job search experience for you.
          Stay tuned — new features are on the way!
        </p>
      </div>
    </div>
  );
}
