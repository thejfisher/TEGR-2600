%% Retrieve data
name = 'ExperimentdataB'; %% Select data from one of the three models
load (name);
Solution = zeros(100,1); 
for i =1:100
     Intensity = Experimentdata{i+2,1}; %% Get the detection intensity on the CCD
     Intensity_min = min(Intensity); %% Get the minimum intensity
     Hamiltonian = Experimentdata{i+2,2};  %% Get Hamiltonian 
     index = find(Intensity == Intensity_min);  
     Solution(i,1) = Hamiltonian(index(end));  %% Get the exact solution for each run
end

%% Draw a histogram; Plot Fig6.B
figure;
histogram(Solution,[-25,-20.5,-19.5,-18.5,-17.5,-16.5,-15.5,-14.5,-13.5,-10],'FaceColor',[0.93,0.69,0.13],'EdgeColor','none')
set(gca,'FontWeight','bold')
set(gca,'FontSize',18)


%%  Plot Fig6.E
Index = Experimentdata{1,4};
Temperature = kron(Experimentdata{1,2},ones(1,Experimentdata{1,3}));
figure
for i = Index:Index + 7
    Hamiltonian = Experimentdata{i+2,2};
    plot(Hamiltonian)
    hold on
end
ylim([-22,30]);
yyaxis right
plot(Temperature,'--',LineWidth=1.5,Color='k')
set(gca,'FontSize',18)
set(gca,'FontWeight','bold')


%% Plot insets of Fig6.B
r = 2;
theta = linspace(0,2*pi,17);
x = r*sin(theta);
y = r*cos(theta);
coordi = [x(1:16)',y(1:16)'];
figure;
gplot(Experimentdata{1,1},coordi,'.-')
axis off