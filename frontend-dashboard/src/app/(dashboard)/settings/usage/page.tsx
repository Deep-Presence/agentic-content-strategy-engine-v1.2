import { Activity, Zap, HardDrive, BarChart3 } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { PageHeader } from '@/components/layout/page-header';

export default function UsageSettingsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Usage"
        description="Monitor your platform usage this month"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Pipeline Runs */}
        <Card>
          <CardHeader>
            <CardTitle>Pipeline Runs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-body-sm font-sans text-cream-800">Gap Analysis</span>
                  <span className="text-body-sm font-sans font-semibold text-cream-950">12 / 50</span>
                </div>
                <Progress value={12} max={50} color="ocean" />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-body-sm font-sans text-cream-800">Research</span>
                  <span className="text-body-sm font-sans font-semibold text-cream-950">8 / 50</span>
                </div>
                <Progress value={8} max={50} color="terracotta" />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-body-sm font-sans text-cream-800">Content Generation</span>
                  <span className="text-body-sm font-sans font-semibold text-cream-950">24 / 100</span>
                </div>
                <Progress value={24} max={100} color="sage" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Quick Metrics */}
        <Card>
          <CardHeader>
            <CardTitle>This Month</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-cream-100 rounded-md">
                <Activity className="h-4 w-4 text-ocean-400 mb-1.5" />
                <p className="font-sans text-heading-3 font-semibold text-cream-950">44</p>
                <p className="text-caption text-cream-600">Total Runs</p>
              </div>
              <div className="p-3 bg-cream-100 rounded-md">
                <Zap className="h-4 w-4 text-terracotta-400 mb-1.5" />
                <p className="font-sans text-heading-3 font-semibold text-cream-950">1,247</p>
                <p className="text-caption text-cream-600">API Calls</p>
              </div>
              <div className="p-3 bg-cream-100 rounded-md">
                <HardDrive className="h-4 w-4 text-sage-400 mb-1.5" />
                <p className="font-sans text-heading-3 font-semibold text-cream-950">2.3 GB</p>
                <p className="text-caption text-cream-600">Storage Used</p>
              </div>
              <div className="p-3 bg-cream-100 rounded-md">
                <BarChart3 className="h-4 w-4 text-cream-600 mb-1.5" />
                <p className="font-sans text-heading-3 font-semibold text-cream-950">89%</p>
                <p className="text-caption text-cream-600">Success Rate</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
