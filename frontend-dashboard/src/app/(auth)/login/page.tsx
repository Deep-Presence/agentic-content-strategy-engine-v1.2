import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export default function LoginPage() {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2 mb-4">
          <div className="h-10 w-10 rounded-md bg-terracotta-400 flex items-center justify-center">
            <span className="text-white font-serif font-semibold text-heading-3">D</span>
          </div>
          <span className="font-serif font-semibold text-heading-2 text-cream-950">
            Deep Presence
          </span>
        </div>
        <CardTitle>Sign in</CardTitle>
        <CardDescription>Enter your credentials to access the dashboard</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Input label="Email" type="email" placeholder="you@company.com" />
        <Input label="Password" type="password" placeholder="Enter your password" />
        <Button className="w-full">Sign in</Button>
      </CardContent>
    </Card>
  );
}
