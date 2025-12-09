import { ReactNode } from "react";
import Header from "./Header";
import Sidebar from "./Sidebar";

type MainLayoutProps = {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  showFilters?: boolean;
  selectionMode?: boolean;
  onToggleSelection?: () => void;
  onRefresh?: () => void;
};

const MainLayout = ({
  title,
  subtitle,
  actions,
  children,
  showFilters = false,
  selectionMode,
  onToggleSelection,
  onRefresh,
}: MainLayoutProps) => {
  return (
    <div className="min-h-screen flex flex-col px-4 md:px-6 py-4">
      <Header
        title={title}
        subtitle={subtitle}
        actions={actions}
        selectionMode={selectionMode}
        onToggleSelection={onToggleSelection}
        onRefresh={onRefresh}
        showTimeframeSwitcher={true}
      />
      <div className="flex flex-1 gap-4">
        <Sidebar showFilters={showFilters} />
        <main className="flex-1 space-y-4">{children}</main>
      </div>
    </div>
  );
};

export default MainLayout;
